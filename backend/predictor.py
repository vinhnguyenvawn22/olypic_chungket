"""Inference for CLI and local demonstration. Only the five measured fields enter each model."""

import json
from functools import lru_cache
import numpy as np
import pandas as pd
import joblib
from backend.advisory import advance
from src.revised_model import ROOT, FEATURES, file_hash

NAMES = {
    "btc": "Baseline BTC",
    "goc": "UNETI15 · cấu hình gốc",
    "moi": "UNETI15 · thử nghiệm bổ sung C=0,03",
    "guard": "Logistic gốc + chặn ánh sáng tăng",
    "low": "Logistic gốc, ngưỡng khuyến nghị 0,10",
    "or2": "Hai Logistic + chặn ánh sáng tăng",
    "ort": "Logistic gốc + Logistic quá khứ + chặn",
    "champion": "Mô hình được chọn theo Macro-F1 trên train",
}
ORIGINAL_PATHS = {
    "btc": (
        "outputs/AI04/model.joblib",
        "dbc2a9c1c07f4c83636455a3795c89c719f6967a70500cabaed3855fbd4ca56c",
    ),
    "goc": (
        "model/logistic_optimized.joblib",
        "d63a9b0a5ef8e411ea9021a45b6a48f377be5cf071bb346201913fe539441d38",
    ),
}


@lru_cache(maxsize=8)
def model_for(mode):
    if mode == "low":
        return model_for("goc")[0], .5, .1
    if mode == "guard":
        mode = "goc"
    if mode == "moi":
        lock = json.loads(
            (ROOT / "results/bo_sung/cau_hinh_chot.json").read_text(encoding="utf-8")
        )
        return (
            joblib.load(ROOT / "model/logistic_hieu_dinh.joblib"),
            lock["threshold"],
            lock["low"],
        )
    path, expected = ORIGINAL_PATHS[mode]
    if file_hash(ROOT / path) != expected:
        raise ValueError(f"Tệp trọng số {path} khác bản UNETI15 đã đối chiếu.")
    return joblib.load(ROOT / path), 0.5, 0.2


@lru_cache(maxsize=1)
def improvement_bundle():
    from src.improvement import PROTOCOL

    bundle = joblib.load(ROOT / "model/improvement_bundle.joblib")
    if file_hash(PROTOCOL) != bundle["lock"]["protocol_sha256"]:
        raise ValueError("Protocol cải tiến đã thay đổi sau khi huấn luyện.")
    return bundle


def focused_scores(values, times, bad, mode):
    from src.improvement import centered_max

    bundle = improvement_bundle()
    key = bundle["lock"]["model"] if mode == "champion" else mode
    output = np.full(len(values), np.nan)
    seconds = times.diff().dt.total_seconds().to_numpy()
    reach = np.isfinite(seconds) & (seconds > 0) & (seconds <= 120)
    starts = np.flatnonzero(~bad & (~reach | np.r_[True, bad[:-1]]))
    for start in starts:
        end = start + 1
        while end < len(values) and not bad[end] and reach[end]:
            end += 1
        block = values.iloc[start:end].reset_index(drop=True).copy()
        block["date"] = times.iloc[start:end].reset_index(drop=True)
        models = bundle["models"]
        if key in {"or2", "ort"}:
            other = "lr2" if key == "or2" else "temporal"
            threshold = 0.7 if key == "or2" else 0.625
            p = centered_max(
                models["goc"].score(block), models[other].score(block), threshold
            )
        else:
            p = models[key].score(block)
        output[start:end] = p
    return output


def predict_sequence(frame, mode="or2"):
    if mode not in NAMES:
        raise ValueError("Phương án mô hình không hợp lệ.")
    focused = mode in {"or2", "ort", "champion"}
    if focused:
        model, threshold, low = (
            None,
            (improvement_bundle()["lock"]["threshold"] if mode == "champion" else 0.5),
            0.2,
        )
    else:
        model, threshold, low = model_for(mode)
    missing = set(FEATURES) - set(frame.columns)
    if missing:
        raise ValueError("Thiếu cột " + ", ".join(sorted(missing)))
    if not 1 <= len(frame) <= 25000:
        raise ValueError("Chuỗi phải có từ 1 đến 25.000 mẫu.")
    values = (
        frame[FEATURES].apply(pd.to_numeric, errors="coerce").reset_index(drop=True)
    )
    if "date" in frame:
        times = pd.to_datetime(
            frame["date"].reset_index(drop=True),
            errors="coerce",
            utc=True,
            format="mixed",
        ).dt.tz_localize(None)
    else:
        times = pd.Series(pd.date_range("2000-01-01", periods=len(values), freq="min"))
    # Boundaries of physical possibility here only protect demo inputs; all reference rows pass.
    bad = (~np.isfinite(values.to_numpy())).any(axis=1) | times.isna().to_numpy()
    bad |= (
        (values.Humidity < 0)
        | (values.Humidity > 100)
        | (values.Light < 0)
        | (values.CO2 < 0)
        | (values.HumidityRatio < 0)
        | (values.Temperature < -273.15)
    ).to_numpy()
    prob = np.full(len(values), np.nan)
    if focused:
        prob = focused_scores(values, times, bad, mode)
    elif (~bad).any():
        prob[~bad] = model.predict_proba(values.loc[~bad])[
            :, list(model.classes_).index(1)
        ]
    count, previous, previous_light = 0, None, None
    guard_enabled = mode in {"guard", "or2", "ort"}
    guard_config = improvement_bundle()["lock"]["guard"] if guard_enabled else None
    records = []
    for i, (p, t) in enumerate(zip(prob, times)):
        if bad[i]:
            count, previous, previous_light = 0, None, None
            fields = [name for name in FEATURES if not np.isfinite(values.loc[i, name])]
            if pd.isna(t):
                fields.append("date")
            why = (
                "Kiểm tra "
                + (", ".join(fields) if fields else "giới hạn vật lý của cảm biến")
                + ". Chuỗi bắt đầu lại ở mẫu hợp lệ tiếp theo."
            )
            pred, action = None, False
        else:
            count, action, why = advance(
                float(p),
                t,
                count,
                previous,
                threshold=low,
                max_gap=None if mode == "btc" else 120,
            )
            jump = (
                guard_enabled
                and previous is not None
                and previous_light is not None
                and 0 < (t - previous).total_seconds() <= 120
                and guard_config["delta_lux"] is not None
                and values.Light.iloc[i] - previous_light > guard_config["delta_lux"]
            )
            if jump:
                count, action = 0, False
                why = (
                    f"Ánh sáng tăng {values.Light.iloc[i] - previous_light:.2f} lux, "
                    f"vượt mốc học từ train {guard_config['delta_lux']:.2f} lux. "
                    "Hủy chuỗi phòng trống và tiếp tục theo dõi."
                )
            pred = int(p >= threshold)
            previous, previous_light = t, values.Light.iloc[i]
        records.append(
            dict(
                sample=i + 1,
                date=str(t) if not pd.isna(t) else "",
                score=None if not np.isfinite(p) else float(p),
                prediction=pred,
                state="Dữ liệu cần kiểm tra"
                if pred is None
                else "Có người"
                if pred
                else "Trống",
                streak=count,
                recommend=bool(action),
                reason=why,
                classification_threshold=threshold,
                advisory_threshold=low,
            )
        )
    return records
