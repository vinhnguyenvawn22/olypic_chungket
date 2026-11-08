"""Measure the three already-defined alternatives on the same validation and compute event evidence."""

import json
import numpy as np
import pandas as pd
from backend.predictor import predict_sequence
from src.revised_model import ROOT, read_sensors, classification, save_json, file_hash


def episode_ledger(frame):
    empty = frame.Occupancy.eq(0)
    delta = frame.date.diff().dt.total_seconds()
    change = empty.ne(empty.shift()) | ~delta.between(0, 120, inclusive="right")
    rows = []
    for _, block in frame[empty].groupby(change.cumsum()[empty]):
        row = {
            "start": str(block.date.iloc[0]),
            "end": str(block.date.iloc[-1]),
            "n": len(block),
        }
        for mode in ["btc", "goc", "moi"]:
            hits = np.flatnonzero(block[mode + "_alert"])
            row[mode + "_rows"] = len(hits)
            row[mode + "_first_delay_samples"] = int(hits[0]) if len(hits) else None
        rows.append(row)
    return pd.DataFrame(rows)


def block_intervals(frame):
    rng = np.random.default_rng(2026)
    n = len(frame)
    y = frame.Occupancy.to_numpy()
    names = ["btc", "goc", "moi"]
    pred = [frame[n + "_prediction"].to_numpy() for n in names]
    diffs = []
    for _ in range(1000):
        start = rng.integers(0, n, (n + 59) // 60)
        ix = ((start[:, None] + np.arange(60)) % n).ravel()[:n]
        f = []
        for v in pred:
            truth = y[ix]
            a = v[ix]
            tp = np.sum((a == 1) & (truth == 1))
            tn = np.sum((a == 0) & (truth == 0))
            errors = np.sum(a != truth)
            f.append(
                0.5
                * (2 * tp / max(1, 2 * tp + errors) + 2 * tn / max(1, 2 * tn + errors))
            )
        diffs.append([100 * (f[1] - f[0]), 100 * (f[2] - f[1])])
    return {
        name: np.quantile(np.array(diffs)[:, i], [0.025, 0.975]).tolist()
        for i, name in enumerate(["goc_minus_btc_pp", "moi_minus_goc_pp"])
    }


def main():
    out = ROOT / "results/bo_sung"
    lock = json.loads((out / "cau_hinh_chot.json").read_text())
    assert file_hash(ROOT / "protocol_bo_sung.json") == lock["protocol_sha256"]
    frame = read_sensors(ROOT / "data/AI04/datatest.txt")
    y = frame.Occupancy.to_numpy()
    rows = []
    for mode in ["btc", "goc", "moi"]:
        records = pd.DataFrame(predict_sequence(frame, mode))
        p = records.prediction.to_numpy()
        a = records.recommend.to_numpy()
        m = classification(y, p)
        m.update(
            variant=mode,
            unsafe=int(np.sum(a & (y == 1))),
            good=int(np.sum(a & (y == 0))),
            coverage=float(a[y == 0].mean()),
            recall=float(1 - m["FER"]),
        )
        for col, key in [
            ("prediction", "prediction"),
            ("recommend", "alert"),
            ("score", "score"),
            ("streak", "streak"),
        ]:
            frame[mode + "_" + key] = records[col].to_numpy()
        rows.append(m)
    ledger = episode_ledger(frame)
    ledger.to_csv(out / "cac_dot_trong.csv", index=False)
    for row in rows:
        row["hit_episodes"] = int((ledger[row["variant"] + "_rows"] > 0).sum())
        row["empty_episodes"] = len(ledger)
    table = pd.DataFrame(rows)
    table.to_csv(out / "validation_ba_phuong_an.csv", index=False)
    print(table.to_string(index=False))
    frame.to_csv(out / "du_doan_validation.csv", index=False)
    changed = frame.goc_prediction != frame.moi_prediction
    save_json(
        out / "chan_doan.json",
        {
            "paired_block_bootstrap": block_intervals(frame),
            "resampling": "1.000 bootstrap ghép cặp, khối tròn 60 dòng, seed 2026. Khoảng mô tả, validation đã từng xem.",
            "new_corrected": int((changed & (frame.moi_prediction == y)).sum()),
            "new_errors": int((changed & (frame.moi_prediction != y)).sum()),
            "validation_previously_examined": True,
            "unsafe_case_goc": frame.loc[
                frame.goc_alert & frame.Occupancy.eq(1),
                ["date", "Light", "CO2", "goc_score", "goc_streak"],
            ]
            .astype({"date": str})
            .to_dict("records"),
            "validation_gaps_over_120": int(
                (frame.date.diff().dt.total_seconds() > 120).sum()
            ),
        },
    )


if __name__ == "__main__":
    main()
