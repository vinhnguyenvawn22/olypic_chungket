"""Thực nghiệm tập trung vào mô hình và khuyến nghị có trạng thái.

Selection and guard fitting read training data only. Official validation has
been examined historically. Its results are reported as development evidence.
"""

import argparse
from dataclasses import dataclass
import json
import warnings

import joblib
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.discriminant_analysis import (
    LinearDiscriminantAnalysis,
    QuadraticDiscriminantAnalysis,
)
from sklearn.ensemble import (
    ExtraTreesClassifier,
    RandomForestClassifier,
    HistGradientBoostingClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from threadpoolctl import threadpool_limits

from src.revised_model import (
    ROOT,
    FEATURES,
    build_model,
    classification,
    file_hash,
    forward_days,
    read_sensors,
    save_json,
)

RESULT = ROOT / "results/cai_tien"
PROTOCOL = ROOT / "research/protocol_cai_tien.json"
NAMES = {
    "btc": "BTC Logistic 5 cảm biến",
    "goc": "UNETI15 Logistic đa thức",
    "lr2": "Logistic Light+CO₂",
    "lda": "LDA Light+CO₂",
    "qda": "QDA Light+CO₂",
    "svm": "SVM RBF Light+CO₂",
    "rf": "Random Forest 5 cảm biến",
    "et": "Extra Trees 5 cảm biến",
    "hgb5": "HGB 5 cảm biến",
    "hgb2": "HGB Light+CO₂",
    "mono": "HGB đơn điệu Light+CO₂",
    "temporal": "Logistic với tín hiệu quá khứ",
    "or2": "OR Logistic đa thức và 2 cảm biến",
    "ort": "OR Logistic đa thức và quá khứ",
}
BASE = list(NAMES)[:12]
POLICIES = ["three", "five", "ten", "delta", "cooldown", "dark"]


def connected(frame):
    seconds = pd.to_datetime(frame.date).diff().dt.total_seconds().to_numpy()
    return np.isfinite(seconds) & (seconds > 0) & (seconds <= 120)


def features(frame, mode):
    raw = frame[FEATURES].reset_index(drop=True).copy()
    if mode == "raw5":
        return raw
    if mode == "two":
        return raw[["Light", "CO2"]]
    reach = connected(frame)
    groups = np.cumsum(~reach)
    t = (frame.date - frame.date.iloc[0]).dt.total_seconds().to_numpy() / 60
    output = raw[["Light", "CO2"]].copy()
    delta = raw.Light.diff().to_numpy()
    logdelta = np.log1p(raw.Light).diff().to_numpy()
    delta[~reach] = 0
    logdelta[~reach] = 0
    output["Light_up"] = np.maximum(delta, 0)
    output["Light_down"] = np.maximum(-delta, 0)
    output["logLight_up"] = np.maximum(logdelta, 0)
    output["logLight_down"] = np.maximum(-logdelta, 0)
    for count in (3, 10):
        slopes = np.zeros(len(frame))
        for group in np.unique(groups):
            idx = np.flatnonzero(groups == group)
            tt, co2 = t[idx] - t[idx[0]], raw.CO2.to_numpy()[idx]

            def mean(values):
                return pd.Series(values).rolling(count, min_periods=1).mean().to_numpy()

            variance = mean(tt * tt) - mean(tt) ** 2
            covariance = mean(tt * co2) - mean(tt) * mean(co2)
            slopes[idx] = np.divide(
                covariance, variance, out=np.zeros(len(idx)), where=variance > 1e-9
            )
        output[f"CO2_slope{count}"] = slopes
    return output


@dataclass
class Fitted:
    estimator: object
    mode: str
    margin: bool = False

    def score(self, frame):
        x = features(frame, self.mode)
        if self.margin:
            return expit(self.estimator.decision_function(x))
        return self.estimator.predict_proba(x)[
            :, list(self.estimator.classes_).index(1)
        ]


def fit_one(key, frame):
    mode = "two" if key in {"lr2", "lda", "qda", "svm", "hgb2", "mono"} else "raw5"
    y = frame.Occupancy.to_numpy()
    if key in {"btc", "goc"}:
        recipe = ("linear", 1.0, None) if key == "btc" else ("poly2", 0.3, "balanced")
        return Fitted(build_model(recipe).fit(frame[FEATURES], y), "raw5")
    if key in {"lr2", "temporal"}:
        mode = "temporal" if key == "temporal" else "two"
        estimator = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=2000, random_state=2026),
        )
        weight = np.where(y == 1, 4.0, 1.0)
        if key == "temporal":
            starts = ~connected(frame) | (y != np.r_[y[0], y[:-1]])
            episode = np.cumsum(starts)
            counts = np.bincount(episode)
            for label in (0, 1):
                mask = y == label
                reference = np.median(counts[np.unique(episode[mask])])
                local = np.clip(np.sqrt(reference / counts[episode[mask]]), 0.5, 2.0)
                weight[mask] *= local / local.mean()
        estimator.fit(
            features(frame, mode), y, logisticregression__sample_weight=weight
        )
        return Fitted(estimator, mode)
    if key == "lda":
        estimator = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    elif key == "qda":
        estimator = QuadraticDiscriminantAnalysis(reg_param=0.1)
    elif key == "svm":
        estimator = SVC(
            C=3.0, kernel="rbf", gamma="scale", class_weight="balanced", max_iter=30000
        )
    elif key in {"rf", "et"}:
        cls = RandomForestClassifier if key == "rf" else ExtraTreesClassifier
        estimator = cls(
            n_estimators=120,
            max_depth=8,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=2026,
            n_jobs=1,
        )
    else:
        estimator = HistGradientBoostingClassifier(
            max_leaf_nodes=7,
            max_iter=150,
            l2_regularization=5.0,
            early_stopping=False,
            class_weight="balanced",
            monotonic_cst=[1, 1] if key == "mono" else None,
            random_state=2026,
        )
    estimator = make_pipeline(
        SimpleImputer(strategy="median"), StandardScaler(), estimator
    )
    estimator.fit(features(frame, mode), y)
    return Fitted(estimator, mode, key == "svm")


def centered_max(first, second, second_threshold):
    left = logit(np.clip(first, 1e-10, 1 - 1e-10))
    right = logit(np.clip(second, 1e-10, 1 - 1e-10)) - logit(second_threshold)
    return expit(np.maximum(left, right))


def add_fusions(scores):
    scores["or2"] = centered_max(scores["goc"], scores["lr2"], 0.7)
    scores["ort"] = centered_max(scores["goc"], scores["temporal"], 0.625)
    return scores


def fit_guard(frame):
    step = frame.Light.diff().to_numpy()
    y = frame.Occupancy.to_numpy()
    eligible = connected(frame) & (y == 0) & (np.r_[False, y[:-1] == 0]) & (step > 0)
    values = step[eligible & np.isfinite(step)]
    return dict(
        delta_lux=float(np.quantile(values, 0.99)) if len(values) else None,
        positive_empty_steps=int(len(values)),
        dark_lux=float(frame.loc[frame.Occupancy == 1, "Light"].min()),
    )


def policy(frame, score, kind, guard, boundary=None):
    n = len(frame)
    reach = connected(frame)
    if boundary is not None:
        reach &= np.r_[False, boundary[1:] == boundary[:-1]]
    steps = frame.Light.diff().to_numpy()
    action, streak, veto = np.zeros(n, bool), np.zeros(n, int), np.zeros(n, bool)
    required = {"five": 5, "ten": 10}.get(kind, 3)
    run, cooling = 0, 0
    for i, p in enumerate(score):
        if not reach[i]:
            run, cooling = 0, 0
        valid = np.isfinite(p) and np.isfinite(frame.Light.iloc[i])
        jump = (
            reach[i]
            and guard["delta_lux"] is not None
            and steps[i] > guard["delta_lux"]
        )
        block = kind in {"delta", "cooldown"} and jump
        if kind == "cooldown":
            cooling = 3 if block else max(0, cooling - 1)
            block = cooling > 0
        if kind == "dark":
            block = frame.Light.iloc[i] >= guard["dark_lux"]
        veto[i] = bool(block)
        run = run + 1 if valid and p < 0.2 and not block else 0
        streak[i], action[i] = run, run >= required
    return action, streak, veto


def action_metrics(frame, action, boundary=None):
    y = frame.Occupancy.to_numpy()
    reach = connected(frame)
    if boundary is not None:
        reach &= np.r_[False, boundary[1:] == boundary[:-1]]
    starts = np.flatnonzero((y == 0) & (~reach | np.r_[True, y[:-1] != 0]))
    detected, delays = 0, []
    for start in starts:
        end = start + 1
        while end < len(frame) and reach[end] and y[end] == 0:
            end += 1
        hits = np.flatnonzero(action[start:end])
        if len(hits):
            detected += 1
            delays.append(int(hits[0]))
    unsafe = int((action & (y == 1)).sum())
    good = int((action & (y == 0)).sum())
    return dict(
        unsafe=unsafe,
        good=good,
        unsafe_rate=unsafe / int((y == 1).sum()) if (y == 1).any() else None,
        coverage=good / int((y == 0).sum()) if (y == 0).any() else None,
        empty_episodes=len(starts),
        detected_episodes=detected,
        median_delay_samples=float(np.median(delays)) if delays else None,
    )


def splits(frame):
    groups = frame.date.dt.floor("2h")
    kfold = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=2026)
    times = frame.date.astype("int64").to_numpy()
    for i, (learn, hold) in enumerate(kfold.split(frame, frame.Occupancy, groups)):
        # Purge every learning row within ten minutes of any held-out row.
        htime = times[hold]
        pos = np.searchsorted(htime, times[learn])
        previous = htime[np.clip(pos - 1, 0, len(htime) - 1)]
        following = htime[np.clip(pos, 0, len(htime) - 1)]
        distance = np.minimum(
            abs(times[learn] - previous), abs(times[learn] - following)
        )
        learn = learn[distance > 10 * 60 * 1_000_000_000]
        yield "grouped", str(i + 1), learn, hold
    for day, learn, hold in forward_days(frame):
        yield "forward", day, learn, hold


def train_evidence(frame):
    records, predictions = [], []
    for scheme, fold, learn, hold in splits(frame):
        learning = frame.iloc[learn].reset_index(drop=True)
        held = frame.iloc[hold].reset_index(drop=True)
        guard = fit_guard(learning)
        scores = add_fusions({key: fit_one(key, learning).score(held) for key in BASE})
        boundary = (
            held.date.dt.floor("2h").astype("int64").to_numpy()
            if scheme == "grouped"
            else None
        )
        block = held[["date", "Occupancy"]].copy()
        block["scheme"], block["fold"] = scheme, fold
        for key, values in scores.items():
            block[key] = values
            for kind in POLICIES:
                a, _, _ = policy(held, values, kind, guard, boundary)
                block[key + "_" + kind] = a
        predictions.append(block)
        records.append(
            dict(
                scheme=scheme,
                fold=fold,
                learning=len(learn),
                held=len(hold),
                occupied=int(held.Occupancy.sum()),
                **guard,
            )
        )
    return pd.concat(predictions, ignore_index=True), records


def rank_models(evidence):
    rows = []
    for index, key in enumerate(NAMES):
        thresholds = sorted(
            set(
                [0.35, 0.5, 0.65, 0.8]
                + ([0.7] if key == "lr2" else [0.625] if key == "temporal" else [])
            )
        )
        for threshold in thresholds:
            row = dict(
                model=key,
                name=NAMES[key],
                threshold=threshold,
                complexity=2 if key.startswith("or") else 1,
                order=index,
            )
            for scheme in ("grouped", "forward"):
                part = evidence[evidence.scheme == scheme]
                m = classification(
                    part.Occupancy.to_numpy(), part[key].to_numpy() >= threshold
                )
                row.update({scheme + "_" + k: v for k, v in m.items()})
            row["eligible"] = (
                max(row["grouped_FER"], row["forward_FER"]) <= 0.01
                and max(row["grouped_FPR"], row["forward_FPR"]) <= 0.08
            )
            row["worst_f1"] = min(row[s + "_Macro_F1"] for s in ("grouped", "forward"))
            row["mean_f1"] = np.mean(
                [row[s + "_Macro_F1"] for s in ("grouped", "forward")]
            )
            row["cost"] = np.mean(
                [
                    (5 * row[s + "_FN"] + row[s + "_FP"]) / row[s + "_n"]
                    for s in ("grouped", "forward")
                ]
            )
            rows.append(row)
    grid = pd.DataFrame(rows)
    eligible = grid[grid.eligible]
    fallback = eligible.empty
    ranked = (grid if fallback else eligible).sort_values(
        (["cost"] if fallback else [])
        + ["worst_f1", "mean_f1", "complexity", "order", "threshold"],
        ascending=([True] if fallback else []) + [False, False, True, True, True],
    )
    best = ranked.iloc[0]
    return dict(
        model=best.model, threshold=float(best.threshold), fallback=bool(fallback)
    ), grid


def rank_policies(evidence, key):
    rows = []
    for index, kind in enumerate(POLICIES):
        row = dict(policy=kind, order=index)
        for scheme in ("grouped", "forward"):
            part = evidence[evidence.scheme == scheme]
            y, a = part.Occupancy.to_numpy(), part[key + "_" + kind].to_numpy(bool)
            row[scheme + "_unsafe"] = int((a & (y == 1)).sum())
            row[scheme + "_rate"] = row[scheme + "_unsafe"] / int((y == 1).sum())
            row[scheme + "_coverage"] = int((a & (y == 0)).sum()) / int((y == 0).sum())
        row["worst_rate"] = max(row[s + "_rate"] for s in ("grouped", "forward"))
        row["min_coverage"] = min(row[s + "_coverage"] for s in ("grouped", "forward"))
        rows.append(row)
    grid = pd.DataFrame(rows)
    eligible = grid[grid.min_coverage >= 0.9]
    if eligible.empty:
        return {"policy": "delta", "fallback": True}, grid
    best = eligible.sort_values(
        ["worst_rate", "min_coverage", "order"], ascending=[True, False, True]
    ).iloc[0]
    return {"policy": best.policy, "fallback": False}, grid


def select(frame):
    evidence, folds = train_evidence(frame)
    model, models = rank_models(evidence)
    action, policies = rank_policies(evidence, model["model"])
    original_action, original_policies = rank_policies(evidence, "goc")
    return (
        {**model, "action": action, "original_action": original_action},
        evidence,
        folds,
        models,
        policies,
        original_policies,
    )


def train():
    RESULT.mkdir(exist_ok=True)
    frame = read_sensors(ROOT / "data/AI04/datatraining.txt")
    lock, evidence, folds, models, policies, original_policies = select(frame)
    lock.update(
        train_sha256=file_hash(ROOT / "data/AI04/datatraining.txt"),
        protocol_sha256=file_hash(PROTOCOL),
        source_sha256=file_hash(__file__),
        guard=fit_guard(frame),
        validation_history="previously inspected development set",
    )
    save_json(RESULT / "selection_locked.json", lock)
    evidence.to_csv(RESULT / "train_oof.csv", index=False)
    pd.DataFrame(folds).to_csv(RESULT / "splits.csv", index=False)
    models.to_csv(RESULT / "model_grid.csv", index=False)
    policies.to_csv(RESULT / "policy_grid_champion.csv", index=False)
    original_policies.to_csv(RESULT / "policy_grid_goc.csv", index=False)
    outer_rows, outer_predictions = [], []
    for day, learn, hold in forward_days(frame):
        learning, held = (
            frame.iloc[learn].reset_index(drop=True),
            frame.iloc[hold].reset_index(drop=True),
        )
        if list(forward_days(learning)):
            inner, *_ = select(learning)
        else:
            inner = dict(
                model="goc",
                threshold=0.5,
                action=dict(policy="delta", fallback=True),
                original_action=dict(policy="delta", fallback=True),
            )
        guard = fit_guard(learning)
        scores = add_fusions({key: fit_one(key, learning).score(held) for key in BASE})
        cases = [
            ("btc", scores["btc"], 0.5, "three"),
            ("goc", scores["goc"], 0.5, "three"),
            ("goc_delta", scores["goc"], 0.5, "delta"),
            (
                "selected",
                scores[inner["model"]],
                inner["threshold"],
                inner["action"]["policy"],
            ),
        ]
        for name, p, threshold, kind in cases:
            action, _, _ = policy(held, p, kind, guard)
            row = dict(
                day=day,
                variant=name,
                model=inner["model"] if name == "selected" else name,
                threshold=threshold,
                policy=kind,
                **classification(held.Occupancy.to_numpy(), p >= threshold),
                **action_metrics(held, action),
            )
            outer_rows.append(row)
            outer_predictions.append(
                pd.DataFrame(
                    dict(
                        date=held.date,
                        Occupancy=held.Occupancy,
                        day=day,
                        variant=name,
                        score=p,
                        prediction=p >= threshold,
                        recommend=action,
                    )
                )
            )
        print("nested day", day, inner["model"], inner["threshold"], flush=True)
    pd.DataFrame(outer_rows).to_csv(RESULT / "nested_days.csv", index=False)
    outer = pd.concat(outer_predictions, ignore_index=True)
    outer.to_csv(RESULT / "nested_predictions.csv", index=False)
    summaries = []
    for key, part in outer.groupby("variant", sort=False):
        y, a = part.Occupancy.to_numpy(), part.recommend.to_numpy(bool)
        summaries.append(
            dict(
                variant=key,
                **classification(y, part.prediction.to_numpy()),
                unsafe=int((a & (y == 1)).sum()),
                good=int((a & (y == 0)).sum()),
                coverage=int((a & (y == 0)).sum()) / int((y == 0).sum()),
            )
        )
    pd.DataFrame(summaries).to_csv(RESULT / "nested_summary.csv", index=False)
    fitted = {key: fit_one(key, frame) for key in BASE}
    joblib.dump(
        dict(models=fitted, lock=lock), ROOT / "model/improvement_bundle.joblib"
    )
    print(json.dumps(lock, ensure_ascii=False), flush=True)


def score_bundle(bundle, frame):
    return add_fusions(
        {key: model.score(frame) for key, model in bundle["models"].items()}
    )


def evaluate():
    bundle = joblib.load(ROOT / "model/improvement_bundle.joblib")
    lock = bundle["lock"]
    if file_hash(PROTOCOL) != lock["protocol_sha256"]:
        raise ValueError("Protocol đã thay đổi sau khi chốt.")
    frame = read_sensors(ROOT / "data/AI04/datatest.txt")
    scores = score_bundle(bundle, frame)
    rows, detail = [], frame.copy()
    for key, p in scores.items():
        threshold = (
            lock["threshold"]
            if key == lock["model"]
            else 0.7
            if key == "lr2"
            else 0.625
            if key == "temporal"
            else 0.5
        )
        detail[key + "_score"] = p
        detail[key + "_prediction"] = p >= threshold
        for kind in POLICIES:
            action, streak, veto = policy(frame, p, kind, lock["guard"])
            rows.append(
                dict(
                    model=key,
                    name=NAMES[key],
                    threshold=threshold,
                    policy=kind,
                    selected_model=key == lock["model"],
                    **classification(frame.Occupancy.to_numpy(), p >= threshold),
                    **action_metrics(frame, action),
                )
            )
            detail[key + "_" + kind + "_recommend"] = action
            if key == "goc" and kind == "delta":
                detail["goc_delta_streak"], detail["delta_veto"] = streak, veto
    pd.DataFrame(rows).to_csv(RESULT / "validation_all_development.csv", index=False)
    detail.to_csv(RESULT / "validation_predictions.csv", index=False)
    selected = pd.DataFrame(rows)
    mask = (
        ((selected.model.isin(["btc", "goc"])) & (selected.policy == "three"))
        | ((selected.model == "goc") & (selected.policy == "delta"))
        | (
            (selected.model == lock["model"])
            & (selected.policy == lock["action"]["policy"])
        )
    )
    selected[mask].to_csv(RESULT / "validation_decisions.csv", index=False)
    print(selected[mask].to_string(index=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["train", "evaluate"])
    args = parser.parse_args()
    with threadpool_limits(limits=1), warnings.catch_warnings():
        warnings.simplefilter("error", category=RuntimeWarning)
        (train if args.phase == "train" else evaluate)()


if __name__ == "__main__":
    from src.improvement import main as canonical_main

    canonical_main()
