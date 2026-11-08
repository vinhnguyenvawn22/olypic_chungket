"""Chọn mô hình và ngưỡng hoàn toàn trong datatraining; không đọc validation chính thức."""

from pathlib import Path
import argparse
import hashlib
import json
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, SplineTransformer, StandardScaler
from threadpoolctl import threadpool_limits
from backend.advisory import advance

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["Temperature", "Humidity", "Light", "CO2", "HumidityRatio"]
SEED = 2026
BASELINE = ("linear", 1.0, None)
ORIGINAL = ("poly2", 0.3, "balanced")
SCHEMES = ("grouped", "forward")


def read_sensors(path):
    frame = pd.read_csv(path, index_col=0)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    return frame.sort_values("date", kind="stable").reset_index(drop=True)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, payload):
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def parameter_name(recipe):
    family, strength, weighting = recipe
    return f"{family}, C={strength:g}, w={weighting or 'none'}"


def build_model(recipe):
    family, strength, weighting = recipe
    steps = [SimpleImputer(strategy="median")]
    if family == "poly2":
        steps.append(PolynomialFeatures(degree=2, include_bias=False))
    elif family == "spline":
        steps.append(
            SplineTransformer(
                degree=2,
                n_knots=4,
                knots="uniform",
                include_bias=False,
                extrapolation="constant",
            )
        )
    steps.append(StandardScaler())
    max_iter = 1000 if recipe == BASELINE else 1500
    steps.append(
        LogisticRegression(
            C=strength,
            class_weight=weighting,
            solver="lbfgs",
            random_state=SEED,
            max_iter=max_iter,
        )
    )
    return make_pipeline(*steps)


def forward_days(frame):
    days = frame.date.dt.normalize()
    for day in sorted(days.unique()):
        hold = np.flatnonzero(days == day)
        cutoff = frame.date.iloc[hold].min() - pd.Timedelta(hours=2)
        learn = np.flatnonzero(frame.date < cutoff)
        labels = frame.Occupancy.iloc[learn]
        if labels.nunique() == 2 and labels.sum() >= 100:
            yield str(pd.Timestamp(day).date()), learn, hold


def classification(y, pred):
    tn, fp, fn, tp = map(int, confusion_matrix(y, pred, labels=[0, 1]).ravel())

    def ratio(a, b):
        return a / b if b else None

    occupied_f1 = ratio(2 * tp, 2 * tp + fn + fp)
    empty_f1 = ratio(2 * tn, 2 * tn + fn + fp)
    return dict(
        n=len(y),
        TN=tn,
        FP=fp,
        FN=fn,
        TP=tp,
        FER=ratio(fn, fn + tp),
        FPR=ratio(fp, fp + tn),
        Macro_F1=(occupied_f1 + empty_f1) / 2 if fn + tp and tn + fp else None,
    )


def alert_sequence(probabilities, times, low_threshold, boundaries=None):
    flags = np.zeros(len(probabilities), dtype=bool)
    run_counts = np.zeros(len(probabilities), dtype=int)
    count, previous = 0, None
    for i, (p, timestamp) in enumerate(zip(probabilities, times)):
        if boundaries is not None and (i == 0 or boundaries[i] != boundaries[i - 1]):
            count, previous = 0, None
        count, flags[i], _ = advance(
            float(p), timestamp, count, previous, threshold=low_threshold
        )
        run_counts[i] = count
        previous = timestamp
    return flags, run_counts


def learning_predictions(frame, recipes, forward):
    scores = {scheme: np.full((len(recipes), len(frame)), np.nan) for scheme in SCHEMES}
    boundaries = {scheme: np.full(len(frame), -1) for scheme in SCHEMES}
    groups = frame.date.dt.floor("2h")
    grouped = StratifiedGroupKFold(n_splits=3, random_state=SEED, shuffle=True)
    splits = [
        ("grouped", str(i), a, b)
        for i, (a, b) in enumerate(
            grouped.split(frame[FEATURES], frame.Occupancy, groups), 1
        )
    ]
    splits.extend(("forward", day, a, b) for day, a, b in forward)
    records = []
    for k, (scheme, label, learn, hold) in enumerate(splits):
        if frame.Occupancy.iloc[learn].nunique() < 2:
            continue
        records.append(
            dict(
                scheme=scheme,
                fold=label,
                train_n=len(learn),
                valid_n=len(hold),
                occupied=int(frame.Occupancy.iloc[hold].sum()),
            )
        )
        if scheme == "grouped":
            boundaries[scheme][hold] = groups.iloc[hold].astype("int64").to_numpy()
        else:
            boundaries[scheme][hold] = k
        for i, recipe in enumerate(recipes):
            model = build_model(recipe).fit(
                frame.iloc[learn][FEATURES], frame.Occupancy.iloc[learn]
            )
            scores[scheme][i, hold] = model.predict_proba(frame.iloc[hold][FEATURES])[
                :, 1
            ]
    return scores, boundaries, records


def select(frame, protocol):
    days = list(forward_days(frame))
    if (
        not days
        or frame.date.dt.floor("2h").nunique() < 3
        or sum(int(frame.Occupancy.iloc[b].sum()) for _, a, b in days) == 0
    ):
        fallback = dict(
            recipe=ORIGINAL,
            name=parameter_name(ORIGINAL),
            threshold=0.5,
            low=0.2,
            criterion="thiếu dữ liệu kiểm định bên trong, dùng cấu hình gốc",
        )
        return fallback, pd.DataFrame(), pd.DataFrame(), []
    recipes = [
        (family, c, w)
        for family in protocol["families"]
        for c in protocol["C"]
        for w in protocol["class_weight"]
    ]
    scores, boundaries, records = learning_predictions(frame, recipes, days)
    labels = frame.Occupancy.to_numpy()
    rows = []
    for i, recipe in enumerate(recipes):
        for threshold in protocol["classification_thresholds"]:
            row = dict(
                index=i,
                name=parameter_name(recipe),
                threshold=threshold,
                terms={"linear": 5, "poly2": 20, "spline": 20}[recipe[0]],
            )
            for scheme in SCHEMES:
                pc = scores[scheme][i]
                valid = np.isfinite(pc)
                y = labels[valid]
                m = classification(y, pc[valid] >= threshold)
                row.update({scheme + "_" + key: value for key, value in m.items()})
            row["eligible"] = (
                max(row["grouped_FER"], row["forward_FER"]) <= 0.01
                and max(row["grouped_FPR"], row["forward_FPR"]) <= 0.08
            )
            row["worst_f1"] = min(row["grouped_Macro_F1"], row["forward_Macro_F1"])
            row["mean_f1"] = (row["grouped_Macro_F1"] + row["forward_Macro_F1"]) / 2
            row["mean_cost"] = np.mean(
                [(5 * row[s + "_FN"] + row[s + "_FP"]) / row[s + "_n"] for s in SCHEMES]
            )
            rows.append(row)
    grid = pd.DataFrame(rows)
    eligible = grid.loc[grid.eligible]
    fallback = eligible.empty
    rank = (grid if fallback else eligible).sort_values(
        (["mean_cost"] if fallback else [])
        + ["worst_f1", "mean_f1", "terms", "index", "threshold"],
        ascending=([True] if fallback else []) + [False, False, True, True, True],
    )
    best = rank.iloc[0]
    idx = int(best["index"])
    policies = []
    for low in protocol["advisory_thresholds"]:
        if low >= best.threshold:
            continue
        row = {"low": low}
        for scheme in SCHEMES:
            ps = scores[scheme][idx]
            valid = np.isfinite(ps)
            y = labels[valid]
            a, _ = alert_sequence(
                ps[valid], frame.date[valid], low, boundaries[scheme][valid]
            )
            unsafe = int((a & (y == 1)).sum())
            good = int((a & (y == 0)).sum())
            row.update(
                {
                    scheme + "_unsafe": unsafe,
                    scheme + "_unsafe_rate": unsafe / (y == 1).sum(),
                    scheme + "_coverage": good / (y == 0).sum(),
                }
            )
        row["min_coverage"] = min(row["grouped_coverage"], row["forward_coverage"])
        row["max_unsafe_rate"] = max(
            row["grouped_unsafe_rate"], row["forward_unsafe_rate"]
        )
        policies.append(row)
    pol = pd.DataFrame(policies)
    ok = pol.loc[pol.min_coverage >= 0.90]
    pf = ok.empty
    if pf:
        chosen = pol.sort_values(
            ["min_coverage", "max_unsafe_rate", "low"], ascending=[False, True, True]
        ).iloc[0]
    else:
        chosen = ok.sort_values(
            ["max_unsafe_rate", "min_coverage", "low"], ascending=[True, False, True]
        ).iloc[0]
    locked = dict(
        recipe=recipes[idx],
        name=best["name"],
        threshold=float(best.threshold),
        low=float(chosen.low),
        classification_fallback=bool(fallback),
        advisory_fallback=bool(pf),
        criterion="min Macro-F1 hai cách chia sau lọc FER/FPR",
        min_coverage=float(chosen.min_coverage),
    )
    return locked, grid, pol, records


def fit_rollout(learn, hold, recipe, threshold, low):
    fitted = build_model(recipe).fit(learn[FEATURES], learn.Occupancy)
    p = fitted.predict_proba(hold[FEATURES])[:, 1]
    alerts, _ = alert_sequence(p, hold.date, low)
    return p, p >= threshold, alerts


def main():
    out = ROOT / "results/bo_sung"
    out.mkdir(exist_ok=True, parents=True)
    protocol_path = ROOT / "protocol_bo_sung.json"
    train_path = ROOT / "data/AI04/datatraining.txt"
    protocol = json.loads(protocol_path.read_text())
    train = read_sensors(train_path)
    with threadpool_limits(limits=1):
        selected, grid, policy, folds = select(train, protocol)
        selected.update(
            train_sha256=file_hash(train_path),
            protocol_sha256=file_hash(protocol_path),
            source_sha256=file_hash(__file__),
            training_rows=len(train),
            selection_source="datatraining.txt",
        )
        save_json(out / "cau_hinh_chot.json", selected)
        pd.DataFrame(folds).to_csv(out / "chia_tap.csv", index=False)
        grid.to_csv(out / "tim_kiem_tren_train.csv", index=False)
        policy.to_csv(out / "chon_nguong_de_xuat.csv", index=False)
        fitted = build_model(tuple(selected["recipe"])).fit(
            train[FEATURES], train.Occupancy
        )
        joblib.dump(fitted, ROOT / "model/logistic_hieu_dinh.joblib")
        print("Chốt từ train", selected, flush=True)
        parts = []
        details = []
        for day, a, b in forward_days(train):
            learn = train.iloc[a].reset_index(drop=True)
            hold = train.iloc[b].reset_index(drop=True)
            inner, *_ = select(learn, protocol)
            variants = [
                ("btc", BASELINE, 0.5, 0.2),
                ("goc", ORIGINAL, 0.5, 0.2),
                ("moi", tuple(inner["recipe"]), inner["threshold"], inner["low"]),
            ]
            part = hold[["date", "Occupancy"]].copy()
            part["day"] = day
            for key, recipe, t, low in variants:
                prob, pred, alerts = fit_rollout(learn, hold, recipe, t, low)
                part[key + "_pred"] = pred
                part[key + "_alert"] = alerts
                detail = classification(hold.Occupancy, pred)
                detail.update(
                    day=day,
                    variant=key,
                    learning=len(learn),
                    occupied=int(hold.Occupancy.sum()),
                    model=parameter_name(recipe),
                    threshold=t,
                    low=low,
                    unsafe=int((alerts & (hold.Occupancy.to_numpy() == 1)).sum()),
                    good=int((alerts & (hold.Occupancy.to_numpy() == 0)).sum()),
                    selection=inner["criterion"]
                    if key == "moi"
                    else "cấu hình cố định",
                )
                details.append(detail)
            parts.append(part)
            print(day, inner["name"], inner["threshold"], inner["low"], flush=True)
        outer = pd.concat(parts, ignore_index=True)
        outer.to_csv(out / "du_doan_khoi_ngoai.csv", index=False)
        pd.DataFrame(details).to_csv(out / "ket_qua_theo_ngay.csv", index=False)
        rows = []
        for key in ["btc", "goc", "moi"]:
            row = classification(outer.Occupancy, outer[key + "_pred"])
            row.update(
                variant=key,
                unsafe=int((outer[key + "_alert"] & (outer.Occupancy == 1)).sum()),
                good=int((outer[key + "_alert"] & (outer.Occupancy == 0)).sum()),
            )
            rows.append(row)
        pd.DataFrame(rows).to_csv(out / "tong_hop_khoi_ngoai.csv", index=False)
        print(pd.DataFrame(rows).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
