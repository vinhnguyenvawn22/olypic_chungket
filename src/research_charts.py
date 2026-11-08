"""Biểu đồ từ dữ liệu đang được xử lý trong notebook UNETI15."""

import hashlib
from pathlib import Path
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

COLORS = ["#667C8C", "#137765"]
RED = "#AF4B36"
FEATURE_LABELS = {
    "Temperature": "Nhiệt độ (°C)",
    "Humidity": "Độ ẩm (%)",
    "Light": "Độ rọi (lux)",
    "CO2": "Nồng độ CO₂ (ppm)",
    "HumidityRatio": "Tỷ số ẩm (kg/kg)",
}


def number(value, digits=0):
    return f"{value:,.{digits}f}".translate(str.maketrans({",": ".", ".": ","}))


def percent(value):
    return number(100 * value, 1) + "%"


def panels(rows=1, cols=1, size=(9, 4.2)):
    fig, axes = plt.subplots(rows, cols, figsize=size, layout="constrained")
    for ax in np.asarray(axes).reshape(-1):
        ax.spines[["right", "top"]].set_visible(False)
        ax.set_axisbelow(True)
    return fig, axes


class FigureBook:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=True, parents=True)
        self.records = []
        self.typography = {"font": "DejaVu Sans"}
        plt.rcParams.update(
            {
                "font.family": "DejaVu Sans",
                "font.size": 11,
                "axes.titleweight": "bold",
                "figure.dpi": 100,
            }
        )

    def save(self, figure, filename, title, message):
        if filename[:2] not in {"01", "02", "03", "07", "08", "09", "11"}:
            return
        path = self.directory / filename
        figure.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
        self.records.append(
            {
                "title": title,
                "message": message,
                "png": filename,
                "png_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    def write_index(self):
        lines = ["# Hình nghiên cứu UNETI15", ""]
        for record in self.records:
            lines.extend(
                [
                    f"- [{record['title']}](bieu_do/{record['png']}) · {record['message']}",
                    "",
                ]
            )
        (self.directory.parent / "muc_luc_bieu_do.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )


def class_distribution(counts):
    fig, ax = panels(size=(8, 3))
    ax.barh(["Trống", "Có người"], counts, color=COLORS)
    ax.set(
        xlabel="Số mẫu huấn luyện",
        title="Phân bố trạng thái trong tập huấn luyện",
        xlim=(0, max(counts) * 1.18),
    )
    ax.invert_yaxis()
    for i, n in enumerate(counts):
        ax.text(n + 70, i, number(n), va="center")
    return fig


def signal_distribution(frame, feature):
    fig, ax = panels()
    limit = frame[feature].quantile(0.995)
    bins = np.linspace(frame[feature].min(), limit, 35)
    for y, color, caption in zip([0, 1], COLORS, ["Trống", "Có người"]):
        values = frame.loc[frame.Occupancy == y, feature]
        weights = np.ones(len(values)) * 100 / len(values)
        ax.hist(
            values,
            bins=bins,
            weights=weights,
            histtype="step",
            linewidth=2.5,
            color=color,
            label=caption,
        )
    ax.set(
        xlabel=FEATURE_LABELS[feature],
        ylabel="Tỷ lệ trong từng lớp (%)",
        title="Phân bố "
        + FEATURE_LABELS[feature].split(" (")[0].lower()
        + " theo nhãn (train)",
    )
    ax.legend(frameon=False)
    return fig


def temperature_humidity(frame):
    fig, ax = panels()
    for y, color, label in zip([0, 1], COLORS, ["Trống", "Có người"]):
        part = frame[frame.Occupancy == y]
        ax.scatter(
            part.Temperature, part.Humidity, s=6, alpha=0.2, color=color, label=label
        )
        ax.scatter(
            part.Temperature.median(),
            part.Humidity.median(),
            marker="x",
            color=color,
            s=130,
            linewidth=3,
        )
    ax.set(xlabel=FEATURE_LABELS["Temperature"], ylabel=FEATURE_LABELS["Humidity"])
    ax.legend(frameon=False)
    return fig


def correlation(matrix):
    fig, ax = panels(size=(6.6, 5))
    im = ax.imshow(matrix, cmap="BrBG", vmin=-1, vmax=1)
    names = ["Nhiệt độ", "Độ ẩm", "Độ rọi", "CO₂", "Tỷ số ẩm"]
    ax.set_xticks(range(5), names, rotation=25, ha="right")
    ax.set_yticks(range(5), names)
    for i in range(5):
        for j in range(5):
            x = matrix.iloc[i, j]
            ax.text(
                j,
                i,
                number(x, 2),
                va="center",
                ha="center",
                color="white" if abs(x) > 0.7 else "#182F39",
            )
    fig.colorbar(im, ax=ax, shrink=0.8)
    return fig


def temporal_signals(frame, day):
    fig, axes = panels(3, 1, (10.5, 6.4))
    for ax, col, color, label in zip(
        axes,
        ["Light", "CO2", "Occupancy"],
        [COLORS[0], COLORS[1], RED],
        ["Độ rọi (lux)", "CO₂ (ppm)", "Nhãn thật"],
    ):
        ax.plot(frame.date, frame[col], lw=1.4, color=color)
        ax.set_ylabel(label)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    axes[0].set_title(f"Tín hiệu ngày {pd.Timestamp(day):%d/%m/%Y}")
    return fig


def cv_comparison(frame, best):
    fig, axes = panels(1, 2, (10.5, 3.4))
    for ax, (protocol, part) in zip(axes, frame.groupby("protocol", sort=False)):
        part = part.set_index("model").loc[["BTC Logistic Regression", best]]
        v = 100 * part.macro_f1
        bars = ax.bar(["BTC", "Cải tiến gốc"], v, color=COLORS)
        ax.set_ylim(0, 110)
        ax.set_title(
            "Khối 2 giờ" if "Grouped" in protocol else "Ngày kế tiếp đủ hai lớp"
        )
        ax.set_ylabel("Macro-F1 (%)")
        ax.bar_label(bars, labels=[number(x, 2) for x in v], padding=3)
    return fig


def confusion_matrices(y, predictions):
    fig, axes = panels(1, 2, (9.5, 3.8))
    mats = [confusion_matrix(y, p, labels=[0, 1]) for p in predictions]
    mx = max(m.max() for m in mats)
    for ax, mat, title in zip(axes, mats, ["Baseline BTC", "Logistic cải tiến gốc"]):
        ax.imshow(mat, cmap="GnBu", vmin=0, vmax=mx)
        ax.set_xticks([0, 1], ["Trống", "Có người"])
        ax.set_yticks([0, 1], ["Trống", "Có người"])
        ax.set(xlabel="Dự đoán", ylabel="Nhãn thật", title=title)
        for i in range(2):
            for j in range(2):
                ax.text(
                    j,
                    i,
                    number(mat[i, j]),
                    ha="center",
                    va="center",
                    fontsize=18,
                    fontweight="bold",
                    color="white" if mat[i, j] > mx * 0.5 else "#173346",
                )
        from matplotlib.patches import Rectangle

        ax.add_patch(
            Rectangle((-0.48, 0.52), 0.96, 0.96, fill=False, edgecolor=RED, lw=2.2)
        )
    return fig


def validation_comparison(frame):
    fig, axes = panels(1, 2, (9.2, 3.8))
    for ax, col, label in zip(
        axes, ["macro_f1", "false_empty_rate"], ["Macro-F1 (%)", "False Empty Rate (%)"]
    ):
        v = frame[col] * 100
        bars = ax.bar(["BTC", "Cải tiến gốc"], v, color=COLORS)
        ax.set_ylim(0, v.max() * 1.2)
        ax.set_ylabel(label)
        ax.bar_label(bars, labels=[number(x, 3) for x in v], padding=3)
    return fig


def alert_timeline(frame, threshold, zoom=False):
    fig, axes = panels(2, 1, (10.5, 5.1))
    a, b = axes
    a.plot(frame.date, frame.btc_probability, color=COLORS[0], lw=1.4, label="BTC")
    a.plot(
        frame.date,
        frame.optimized_probability,
        color=COLORS[1],
        lw=1.7,
        label="Cải tiến gốc",
    )
    a.axhline(threshold, color=RED, ls="--", label="Ngưỡng khuyến nghị")
    a.set_ylim(-0.06, 1.08)
    a.set_ylabel("Điểm có người")
    a.legend(ncol=3, frameon=False, fontsize=9)
    b.step(
        frame.date,
        frame.actual,
        where="post",
        lw=1.6,
        color=COLORS[0],
        label="Có người (nhãn thật)",
    )
    b.step(
        frame.date,
        frame.optimized_gap_alert.astype(float) * 0.82,
        where="post",
        lw=1.5,
        color=COLORS[1],
        label="Đang có khuyến nghị",
    )
    bad = frame.optimized_gap_alert & frame.actual.eq(1)
    b.scatter(
        frame.date[bad],
        np.ones(bad.sum()),
        color=RED,
        s=45,
        zorder=4,
        label="Khuyến nghị sai",
    )
    b.set_ylim(-0.12, 1.25)
    b.set_yticks([0, 1], ["Không", "Có"])
    b.legend(
        ncol=3,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.52),
        frameon=False,
        fontsize=9,
    )
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.grid(axis="y", alpha=0.16)
    a.set_title(
        "Thời điểm chuyển trạng thái"
        if zoom
        else "Trạng thái và khuyến nghị trong ngày"
    )
    return fig
