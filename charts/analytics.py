# charts/analytics.py
"""图表层：把清洗后的校园人流数据渲染成 Plotly 图表。

数据来源统一为 data/preprocess.load_clean() 产出的干净数据集，
保证"卡片 → 图表 → 表格 → 地图"看到的都是同一份数据。
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from plotly.subplots import make_subplots

from config import TYPE_COLORS
from data.preprocess import load_clean
from data.weather import fetch_weather_data


def latest_flow(df: pd.DataFrame = None) -> pd.DataFrame:
    """取最新一天的人流数据；df 为空时从清洗结果读取。"""
    df = load_clean() if df is None else df
    latest = df["日期"].max()
    return df[df["日期"] == latest].copy()


def _apply_layout(fig, is_dark: bool, height: int = 350):
    fig.update_layout(
        template="plotly_dark" if is_dark else "plotly",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_type_bar(df: pd.DataFrame = None, is_dark: bool = False):
    """分类对比柱状图：各建筑类型的人流量合计。"""
    flow = latest_flow(df)
    by_type = (
        flow.groupby("类型", as_index=False)["人流量"]
        .sum()
        .sort_values("人流量", ascending=False)
    )

    fig = px.bar(
        by_type, x="类型", y="人流量",
        color="类型", color_discrete_map=TYPE_COLORS, text="人流量",
    )
    fig.update_traces(texttemplate="%{text}", textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="人流量（人次）")
    return _apply_layout(fig, is_dark)


def render_rank_bar(df: pd.DataFrame = None, is_dark: bool = False):
    """建筑人流量排行：横向条形图，按人流从高到低。"""
    flow = latest_flow(df)
    ranked = flow.sort_values("人流量", ascending=True)

    fig = px.bar(
        ranked, x="人流量", y="建筑名称", orientation="h",
        color="人流量", color_continuous_scale="Blues", text="人流量",
    )
    fig.update_traces(texttemplate="%{text}", textposition="outside", cliponaxis=False)
    fig.update_layout(
        showlegend=False, coloraxis_showscale=False,
        xaxis_title=None, yaxis_title=None,
    )
    return _apply_layout(fig, is_dark)


def render_line_chart(is_dark: bool = False):
    """趋势折线图：未来 24 小时温度与降水量（双轴）。"""
    data = fetch_weather_data()
    hourly = pd.DataFrame(data["hourly"])
    hourly["时间"] = pd.to_datetime(hourly["fxTime"]).dt.strftime("%H:00")
    hourly["温度"] = hourly["temp"].astype(float)
    hourly["降水量"] = hourly["precip"].astype(float)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=hourly["时间"], y=hourly["温度"], name="温度 (℃)",
            line=dict(color="#d62728", width=3), mode="lines+markers",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=hourly["时间"], y=hourly["降水量"], name="降水量 (mm)",
            marker_color="#1f77b4", opacity=0.5,
        ),
        secondary_y=True,
    )

    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickangle=-45, nticks=15)
    fig.update_yaxes(title_text="温度 (℃)", secondary_y=False)
    fig.update_yaxes(title_text="降水量 (mm)", secondary_y=True)
    _apply_layout(fig, is_dark, height=330)
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def render_pie_chart(df: pd.DataFrame = None, is_dark: bool = False):
    """占比结构饼图（环形）：各建筑类型的人流占比。

    环下沿几个小扇区（服务、办公等）的外侧标签会互相压字，
    因此只给占比 ≥8% 的类型画外侧标签，小扇区的数值放在
    hover 提示与右侧明细表里，保证图形本身不被文字糊住。
    """
    flow = latest_flow(df)
    by_type = flow.groupby("类型", as_index=False)["人流量"].sum()
    total = by_type["人流量"].sum()
    shares = by_type["人流量"] / total if total else by_type["人流量"] * 0.0

    fig = px.pie(
        by_type, names="类型", values="人流量", hole=0.45,
        color="类型", color_discrete_map=TYPE_COLORS,
    )
    fig.update_traces(
        text=[f"{t} {p:.1%}" if p >= 0.08 else "" for t, p in zip(by_type["类型"], shares)],
        textinfo="text",
        textposition="outside",
        textfont=dict(size=11),
        hovertemplate="%{label}：%{value:,} 人次（%{percent:.1%}）<extra></extra>",
    )
    fig.update_layout(showlegend=False)
    return _apply_layout(fig, is_dark)


def render_table(df: pd.DataFrame = None):
    """明细表：按人流量倒序。"""
    flow = latest_flow(df)
    return (
        flow.sort_values("人流量", ascending=False)[["建筑名称", "类型", "人流量", "使用率(%)"]]
        .reset_index(drop=True)
    )


def render_gauge(df: pd.DataFrame = None, is_dark: bool = False):
    """平均使用率仪表盘（扩展：多维度分析）。"""
    flow = latest_flow(df)
    avg_use = round(float(flow["使用率(%)"].mean()), 1) if len(flow) else 0.0

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=avg_use,
        number={"suffix": "%"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#1f77b4"},
            "steps": [
                {"range": [0, 40], "color": "#fdecea"},
                {"range": [40, 70], "color": "#fff4e5"},
                {"range": [70, 100], "color": "#e8f5e9"},
            ],
        },
        title={"text": "平均使用率"},
    ))
    return _apply_layout(fig, is_dark)


HOURLY_PATH = Path(__file__).resolve().parents[1] / "data" / "campus_flow_hourly.csv"


def render_hourly_line(is_dark: bool = False):
    """分时段人流曲线：全校园按小时汇总，两日对比（早/午/晚高峰）。"""
    hourly = pd.read_csv(HOURLY_PATH, encoding="utf-8-sig")
    fig = px.line(
        hourly, x="小时", y="人流量", color="日期", markers=True,
        color_discrete_sequence=["#1f77b4", "#d62728"],
    )
    for trace in fig.data:
        trace.update(mode="lines+markers", line=dict(width=2.4), marker=dict(size=7))
    fig.update_layout(
        xaxis=dict(dtick=2, title="时刻（时）", range=[-0.5, 23.5]),
        yaxis_title="人流量（人次）",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    return _apply_layout(fig, is_dark, height=330)
