# data/preprocess.py
"""任务2：实验数据准备与预处理。

原始数据 campus_flow_raw.csv 是"模拟数据集"，其中故意注入了若干脏数据，
用来演示预处理流程是否真的生效：

    1) 文本首尾空格（"二号食堂 "、"学习 "）
    2) 完全重复的记录（同一建筑同一天出现多次）
    3) 关键字段缺失（建筑名称为空、人流为空、使用率为 "NA"）
    4) 数值越界（人流量 -50、99999；使用率 120）
    5) 日期格式不统一（2026/11/18 与 2026-11-18 混用）
    6) 点位不在校园建筑清单里（临时摊位，无法上图）

清洗规则：
    - 文本列去首尾空格；日期统一为 YYYY-MM-DD
    - 关键列（日期 / 建筑名称 / 类型 / 人流量）缺失的行直接剔除
    - 人流量限定 [0, 5000]、使用率限定 [0, 100]，越界先置空，再用同类型中位数
      填补；同类型没有可参考值时，退回全局中位数
    - 名称不在校园建筑清单内的记录剔除（没有坐标无法上图）
    - 按 (日期, 建筑名称) 去重，保留首条

输出：campus_flow_clean.csv（utf-8-sig，Excel 直接打开不乱码）。
"""

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RAW_PATH = BASE_DIR / "campus_flow_raw.csv"
CLEAN_PATH = BASE_DIR / "campus_flow_clean.csv"

FLOW_MIN, FLOW_MAX = 0, 5000
RATE_MIN, RATE_MAX = 0, 100

KEY_COLS = ["日期", "建筑名称", "类型", "人流量"]


def load_raw(path: Path = RAW_PATH) -> pd.DataFrame:
    """读原始数据。全部按字符串读入，避免 pandas 自动把脏值吞成 NaN 而看不见。"""
    if not path.exists():
        raise FileNotFoundError(f"原始数据不存在：{path}")
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def known_buildings() -> set:
    """校园建筑清单，用于剔除无法上图的无名点位。"""
    from data.mock import get_campus_data

    return {name.strip() for name in get_campus_data()["名称"]}


def clean_dataframe(raw: pd.DataFrame, buildings: set = None) -> tuple:
    """执行清洗，返回 (干净数据, 清洗报告)。"""
    report = []
    rows_raw = len(raw)
    df = raw.copy()
    df.columns = [c.strip() for c in df.columns]

    # ---- 1. 文本与日期标准化 ----
    df["建筑名称"] = df["建筑名称"].astype(str).str.strip()
    df["类型"] = df["类型"].astype(str).str.strip()
    df["日期"] = pd.to_datetime(
        df["日期"].astype(str).str.replace("/", "-", regex=False), errors="coerce"
    )
    df["人流量"] = pd.to_numeric(df["人流量"], errors="coerce")
    df["使用率(%)"] = pd.to_numeric(df["使用率(%)"], errors="coerce")

    # ---- 2. 关键字段缺失 ----
    missing = df[KEY_COLS].isna().any(axis=1) | (df["建筑名称"] == "") | (df["建筑名称"] == "nan")
    n_missing = int(missing.sum())
    df = df[~missing].copy()
    report.append("剔除关键字段缺失行：%d 条" % n_missing)

    # ---- 3. 数值越界 ----
    flow_bad = (df["人流量"] < FLOW_MIN) | (df["人流量"] > FLOW_MAX)
    rate_bad = (df["使用率(%)"] < RATE_MIN) | (df["使用率(%)"] > RATE_MAX)
    report.append(
        "数值越界：人流量 %d 条、使用率 %d 条 → 置空后按同类型中位数填补"
        % (int(flow_bad.sum()), int(rate_bad.sum()))
    )
    df.loc[flow_bad, "人流量"] = np.nan
    df.loc[rate_bad, "使用率(%)"] = np.nan

    # ---- 4. 中位数填补（同类型优先，退回全局）----
    n_fill = 0
    for col in ("人流量", "使用率(%)"):
        na = df[col].isna()
        n_fill += int(na.sum())
        if na.any():
            by_type = df.groupby("类型")[col].transform("median")
            df[col] = df[col].fillna(by_type)
            df[col] = df[col].fillna(df[col].median())
    report.append("中位数填补空值：%d 个" % n_fill)

    # ---- 5. 清单外的点位 ----
    if buildings:
        unknown = ~df["建筑名称"].isin(buildings)
        n_unknown = int(unknown.sum())
        df = df[~unknown].copy()
        report.append("剔除建筑清单外的点位：%d 条（无坐标无法上图）" % n_unknown)

    # ---- 6. 去重 ----
    rows_before = len(df)
    df = df.drop_duplicates(subset=["日期", "建筑名称"], keep="first").copy()
    report.append("按 (日期, 建筑名称) 去重：删除 %d 条" % (rows_before - len(df)))

    # ---- 7. 收尾：整型化、排序、日期格式化 ----
    df["人流量"] = df["人流量"].round(0).astype(int)
    df["使用率(%)"] = df["使用率(%)"].round(1)
    df = df.sort_values(["日期", "人流量"], ascending=[True, False]).reset_index(drop=True)
    df["日期"] = df["日期"].dt.strftime("%Y-%m-%d")

    report.insert(0, "原始数据 %d 行 → 清洗后 %d 行" % (rows_raw, len(df)))
    return df, report


def build_clean_dataset(verbose: bool = True) -> pd.DataFrame:
    """跑一遍完整清洗，落盘 clean CSV。"""
    df, report = clean_dataframe(load_raw(), known_buildings())
    df.to_csv(CLEAN_PATH, index=False, encoding="utf-8-sig")
    if verbose:
        print("数据清洗报告")
        for line in report:
            print("  -", line)
        print("已写入 %s" % CLEAN_PATH)
    return df


def load_clean() -> pd.DataFrame:
    """读取清洗后的数据；文件不存在时自动重建。"""
    if not CLEAN_PATH.exists():
        return build_clean_dataset(verbose=False)
    return pd.read_csv(CLEAN_PATH, encoding="utf-8-sig")


def kpi_snapshot(df: pd.DataFrame) -> dict:
    """核心指标：总量、均值、环比增长率、峰值建筑。"""
    dates = sorted(df["日期"].unique())
    latest = dates[-1]
    cur = df[df["日期"] == latest]
    total = int(cur["人流量"].sum())
    avg_rate = float(cur["使用率(%)"].mean())

    growth = None
    if len(dates) >= 2:
        prev = df[df["日期"] == dates[-2]]
        prev_total = int(prev["人流量"].sum())
        if prev_total:
            growth = (total - prev_total) / prev_total * 100

    peak = cur.sort_values("人流量", ascending=False).iloc[0]
    return {
        "date": latest,
        "total": total,
        "avg_rate": avg_rate,
        "growth": growth,
        "peak_name": peak["建筑名称"],
        "peak_flow": int(peak["人流量"]),
        "buildings": int(cur["建筑名称"].nunique()),
    }


def with_coords(df: pd.DataFrame) -> pd.DataFrame:
    """给清洗后的记录补上经纬度，供地图渲染；无坐标的记录丢弃。"""
    from data.mock import get_campus_data

    coords = get_campus_data()[["名称", "经度", "纬度"]].rename(columns={"名称": "建筑名称"})
    merged = df.merge(coords, on="建筑名称", how="left")
    return merged.dropna(subset=["经度", "纬度"]).reset_index(drop=True)


if __name__ == "__main__":
    build_clean_dataset()
