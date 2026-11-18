# tools/generate_flow_dataset.py
"""生成可复现的校园人流模拟数据集（答辩用，方案 B）。

设计原则
--------
1. 每栋建筑先定"日接待能力（容量）"，人流量在该容量下按活跃度系数生成；
2. 使用率 = 人流量 / 容量 * 100，严格反算，任何人拿计算器都能对上；
3. 活跃度区间按建筑类型区分，符合校园作息规律（食堂午晚高峰、图书馆自习、
   宿舍白天外流、出入口通勤）；
4. 加入 ±5% 随机噪声，数值不再是整齐的 10 的倍数；
5. 固定随机种子（按 建筑+日期 哈希），任何人重跑结果完全一致；
6. raw 中仍注入脏数据（重复、缺失、越界、斜杠日期、清单外点位），
   用于演示 data/preprocess.py 的清洗流程真实生效。

运行
----
    .venv\\Scripts\\python.exe tools\\generate_flow_dataset.py
"""

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.preprocess import CLEAN_PATH, RAW_PATH, build_clean_dataset  # noqa: E402

# 建筑 -> (类型, 日累计接待容量, 活跃度下限, 活跃度上限)
# 容量口径：教学楼按"同时容纳人数 × 上下课批次"折算日累计人次；
# 食堂按"座位数 × 翻台次数"折算；宿舍按住宿人数进出人次折算。
BASE = {
    # 行知楼为行政办公楼（学工处、教务处办事窗口、报告厅所在），非教学楼，单独归"办公"类
    "行知楼":       ("办公",  900, 0.24, 0.44),
    "教四楼":       ("学习", 2800, 0.52, 0.77),
    "图书馆":       ("学习", 2500, 0.60, 0.86),
    "三号食堂":     ("餐饮", 1000, 0.40, 0.58),   # 规模最小、位置最偏，三食堂里人最少
    "二号食堂":     ("餐饮", 1400, 0.46, 0.64),   # 居中
    "一号食堂":     ("餐饮", 2100, 0.52, 0.72),   # 全校最大食堂，人最多
    "一号组团宿舍": ("住宿", 1500, 0.44, 0.64),
    "二号组团宿舍": ("住宿", 1400, 0.42, 0.62),
    "研究生公寓":   ("住宿",  800, 0.36, 0.56),
    "南大门":       ("出入口", 1500, 0.40, 0.62),   # 傍晚外出觅食、进城人流明显
    "东1门":        ("出入口",  900, 0.28, 0.50),
    "博文后门":     ("出入口",  600, 0.24, 0.46),
    "菜鸟驿站":     ("服务",   900, 0.44, 0.66),
    "校医院":       ("服务",   450, 0.22, 0.42),
    "新体育馆":     ("运动",   900, 0.40, 0.62),
    "田径场":       ("运动",  1000, 0.42, 0.66),
    "终点站":       ("交通",  1400, 0.50, 0.74),
}

DATES = ["2026-11-17", "2026-11-18"]
# 第二天（周三）课更满，整体人流高约 8%
DAY_FACTOR = {"2026-11-17": 1.00, "2026-11-18": 1.08}


def _rng(name: str, date: str) -> np.random.Generator:
    """按 (建筑, 日期) 生成固定种子，保证结果可复现。"""
    seed = int(hashlib.md5(f"{name}|{date}".encode("utf-8")).hexdigest()[:8], 16)
    return np.random.default_rng(seed)


def build_rows() -> list:
    rows = []
    for date in DATES:
        for name, (btype, cap, lo, hi) in BASE.items():
            rng = _rng(name, date)
            activity = lo + (hi - lo) * rng.random()
            activity *= DAY_FACTOR[date]
            # ±5% 噪声，避免数值过于整齐
            activity *= rng.uniform(0.95, 1.05)
            flow = int(round(cap * activity))
            rate = round(flow / cap * 100, 1)
            rows.append({
                "日期": date,
                "建筑名称": name,
                "类型": btype,
                "人流量": flow,
                "使用率(%)": rate,
            })
    return rows


def inject_dirty(rows: list) -> list:
    """注入脏数据，保持清洗演示有效。"""
    dirty = list(rows)

    # 1) 文本首尾空格：把一个真实行改名后追加（清洗后与原名去重）
    dirty.append({"日期": "2026-11-17", "建筑名称": "二号食堂 ", "类型": "餐饮 ",
                  "人流量": "900", "使用率(%)": "70.0"})

    # 2) 完全重复记录（同日同建筑）
    dirty.append(dict(dirty[0]))
    dirty.append(dict(dirty[0]))

    # 3) 关键字段缺失
    dirty.append({"日期": "", "建筑名称": "三号食堂", "类型": "餐饮",
                  "人流量": "1010", "使用率(%)": "55.0"})
    dirty.append({"日期": "2026-11-18", "建筑名称": "", "类型": "学习",
                  "人流量": "880", "使用率(%)": "60.0"})
    dirty.append({"日期": "2026-11-18", "建筑名称": "图书馆", "类型": "学习",
                  "人流量": "", "使用率(%)": "73.0"})
    dirty.append({"日期": "2026-11-17", "建筑名称": "校医院", "类型": "服务",
                  "人流量": "160", "使用率(%)": "NA"})

    # 4) 数值越界
    dirty.append({"日期": "2026-11-17", "建筑名称": "一号食堂", "类型": "餐饮",
                  "人流量": "-50", "使用率(%)": "60.0"})
    dirty.append({"日期": "2026-11-18", "建筑名称": "行知楼", "类型": "办公",
                  "人流量": "99999", "使用率(%)": "88.0"})
    dirty.append({"日期": "2026-11-18", "建筑名称": "新体育馆", "类型": "运动",
                  "人流量": "520", "使用率(%)": "120"})

    # 5) 日期格式不统一（斜杠）
    dirty.append({"日期": "2026/11/18", "建筑名称": "南大门", "类型": "出入口",
                  "人流量": "470", "使用率(%)": "47.0"})

    # 6) 清单外的临时点位（无坐标无法上图）
    dirty.append({"日期": "2026-11-17", "建筑名称": "临时摊位", "类型": "餐饮",
                  "人流量": "210", "使用率(%)": "70.0"})
    dirty.append({"日期": "2026-11-18", "建筑名称": "临时摊位", "类型": "餐饮",
                  "人流量": "180", "使用率(%)": "60.0"})
    return dirty


def build_hourly(clean: pd.DataFrame) -> pd.DataFrame:
    """按校园作息生成分时段人流（与当日总人流严格对齐）。"""

    def shape(h: float) -> float:
        # 早高峰 8:00、午高峰 12:30、晚高峰 18:00，凌晨最低
        return (
            0.06
            + 0.32 * np.exp(-((h - 8.0) ** 2) / (2 * 1.6 ** 2))
            + 0.46 * np.exp(-((h - 12.5) ** 2) / (2 * 1.9 ** 2))
            + 0.38 * np.exp(-((h - 18.0) ** 2) / (2 * 2.2 ** 2))
        )

    hours = list(range(24))
    weights = np.array([shape(h) for h in hours])
    weights = weights / weights.sum()

    rows = []
    for date in clean["日期"].unique():
        total = int(clean.loc[clean["日期"] == date, "人流量"].sum())
        rng = _rng("hourly", str(date))
        noisy = weights * rng.uniform(0.98, 1.02, size=len(weights))
        noisy = noisy / noisy.sum()
        counts = np.floor(noisy * total).astype(int)
        # 把四舍五入的差额补到峰值小时，保证 sum 与当日总量一致
        counts[int(np.argmax(counts))] += total - int(counts.sum())
        for h, c in zip(hours, counts):
            rows.append({"日期": date, "小时": h, "人流量": int(c)})
    return pd.DataFrame(rows)


def main() -> None:
    rows = inject_dirty(build_rows())
    raw = pd.DataFrame(rows, columns=["日期", "建筑名称", "类型", "人流量", "使用率(%)"])
    raw.to_csv(RAW_PATH, index=False, encoding="utf-8-sig")
    print(f"已写入原始数据 {len(raw)} 行 -> {RAW_PATH}")

    clean = build_clean_dataset(verbose=True)

    hourly = build_hourly(clean)
    hourly_path = CLEAN_PATH.parent / "campus_flow_hourly.csv"
    hourly.to_csv(hourly_path, index=False, encoding="utf-8-sig")
    print(f"已写入分时数据 {len(hourly)} 行 -> {hourly_path}")

    # 自洽性校验：使用率必须等于 人流量/容量
    print("\n自洽性校验（抽样 5 条）：")
    for _, r in clean.head(5).iterrows():
        cap = BASE[r["建筑名称"]][1]
        calc = round(r["人流量"] / cap * 100, 1)
        ok = "OK" if abs(calc - r["使用率(%)"]) < 0.05 else "MISMATCH"
        print(f"  {r['日期']} {r['建筑名称']}: {r['人流量']}/{cap} = {calc}% vs 表内 {r['使用率(%)']}% [{ok}]")

    print("\n每日分时合计校验：")
    for date in clean["日期"].unique():
        total = int(clean.loc[clean["日期"] == date, "人流量"].sum())
        hourly_total = int(hourly.loc[hourly["日期"] == date, "人流量"].sum())
        print(f"  {date}: 日汇总 {total} / 分时合计 {hourly_total} -> {'一致' if total == hourly_total else '不一致'}")


if __name__ == "__main__":
    main()
