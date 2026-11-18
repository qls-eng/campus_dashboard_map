# app.py
"""校园地图与天气数据看板 —— 实验2 数据看板设计与实现。

页面结构对应实验任务要求：
    数据概览区（核心指标卡片） / 地图区 / 维度统计区（柱、饼） / 趋势分析区（折线） / 明细数据区（表格）
"""
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from charts.analytics import (
    latest_flow,
    render_gauge,
    render_line_chart,
    render_pie_chart,
    render_rank_bar,
    render_table,
    render_type_bar,
)
from charts.map_view import render_map
from data.preprocess import (
    clean_dataframe,
    known_buildings,
    kpi_snapshot,
    load_clean,
    load_raw,
    with_coords,
)
from data.weather import fetch_weather_data

# 1. 页面基本配置
st.set_page_config(
    page_title="校园地图数据看板",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化 session_state 用于保存坐标记录
if "picked_coords" not in st.session_state:
    st.session_state.picked_coords = []
if "current_lat" not in st.session_state:
    st.session_state.current_lat = 0.0
if "current_lng" not in st.session_state:
    st.session_state.current_lng = 0.0


@st.cache_data(show_spinner=False)
def cleaning_report():
    """缓存一次清洗过程，只取报告文本用于侧边栏展示（不重复落盘）。"""
    _, report = clean_dataframe(load_raw(), known_buildings())
    return report


# 2. 数据加载
flow_df = load_clean()
all_types = sorted(flow_df["类型"].unique())

# 3. 侧边栏
with st.sidebar:
    st.header("⚙️ 设置")
    dark_mode = st.toggle("开启暗色模式", value=False)
    auto_refresh = st.toggle(
        "开启定时刷新（每 60 秒）", value=False,
        help="开启后天气区每 60 秒自动拉取最新数据，仅局部刷新，不阻塞页面操作",
    )
    st.markdown("---")

    st.header("🔎 数据筛选")
    picked_types = st.multiselect(
        "建筑类型", all_types, default=all_types,
        help="筛选后地图、柱状图、饼图与明细表同步更新",
    )
    flow_min = int(flow_df["人流量"].min())
    flow_max = int(flow_df["人流量"].max())
    flow_range = st.slider(
        "人流量范围", min_value=flow_min, max_value=flow_max,
        value=(flow_min, flow_max),
        help="按人流量区间二次筛选，与建筑类型筛选叠加生效",
    )
    st.caption("筛选只影响图表与地图；顶部核心指标始终按全量数据计算。")

    st.markdown("---")

    with st.expander("🧹 数据清洗摘要", expanded=False):
        for line in cleaning_report():
            st.markdown(f"- {line}")

    st.markdown("---")

    st.header("📍 坐标拾取器")
    pick_mode = st.checkbox("开启地图点击拾取")

    if pick_mode:
        st.info(
            "当前点击坐标：\n\n"
            f"纬度: `{st.session_state.current_lat:.6f}`\n\n"
            f"经度: `{st.session_state.current_lng:.6f}`"
        )

        if st.button("➕ 记录当前坐标"):
            if st.session_state.current_lat != 0.0:
                st.session_state.picked_coords.append({
                    "序号": len(st.session_state.picked_coords) + 1,
                    "纬度": round(st.session_state.current_lat, 6),
                    "经度": round(st.session_state.current_lng, 6),
                })
                st.success("已记录！")
            else:
                st.warning("请先在地图上点击一个点")

        if len(st.session_state.picked_coords) > 0:
            st.write("📋 **已记录的坐标列表：**")
            df_coords = pd.DataFrame(st.session_state.picked_coords)
            st.dataframe(df_coords, hide_index=True, width="stretch")

            csv = df_coords.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 下载坐标 CSV (或直接复制)",
                data=csv,
                file_name="picked_coords.csv",
                mime="text/csv",
            )

            if st.button("🗑️ 清空所有记录"):
                st.session_state.picked_coords = []
                st.rerun()
    else:
        st.info("💡 校园地图与交通数据看板")

    st.markdown("---")
    st.download_button(
        label="📥 导出人流明细 CSV",
        data=flow_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="campus_flow_clean.csv",
        mime="text/csv",
        help="导出的是清洗后的完整数据集",
    )

# 4. 动态 CSS 注入
if dark_mode:
    bg_color = "#1a1a24"
    text_color = "#e0e0e0"
    card_bg = "#2a2a35"
    metric_text = "#ffffff"
else:
    bg_color = "#f5f7fa"
    text_color = "#2c3e50"
    card_bg = "#ffffff"
    metric_text = "#1f77b4"

st.markdown(f"""
<style>
    .stApp {{ background-color: {bg_color}; color: {text_color} !important; }}
    h1, h2, h3, h4, h5, h6, p, span, label {{ color: {text_color} !important; }}
    [data-testid="stSidebar"] {{ background-color: {card_bg}; }}
    div[data-testid="stMetric"] {{
        background-color: {card_bg};
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        border-left: 4px solid {metric_text};
    }}
    div[data-testid="stMetricLabel"] > div {{ color: {text_color} !important; opacity: 0.8; }}
    div[data-testid="stMetricValue"] > div {{ color: {metric_text} !important; font-weight: bold; }}
    th {{ color: {text_color} !important; }}
</style>
""", unsafe_allow_html=True)

# 5. 标题
st.title("🏫 校园地图与天气数据看板")
st.caption("📅 数据实时更新 | 桂林理工大学雁山校区")
st.divider()

# 6. 数据概览区（核心指标卡片）
kpi = kpi_snapshot(flow_df)
st.subheader("📌 核心指标")
st.caption(f"统计日期：{kpi['date']}　|　数据来源：清洗后的人流模拟数据集（{len(flow_df)} 条记录）")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        label="总人流量（人次）",
        value=f"{kpi['total']:,}",
        delta=None if kpi["growth"] is None else f"{kpi['growth']:+.1f}% 较前一日",
    )
with c2:
    st.metric(label="平均使用率", value=f"{kpi['avg_rate']:.1f} %")
with c3:
    st.metric(label="人流峰值建筑", value=kpi["peak_name"], delta=f"{kpi['peak_flow']:,} 人次", delta_color="off")
with c4:
    st.metric(label="监测建筑数", value=f"{kpi['buildings']} 个")

# 7. 天气概览（一行文字，避免与核心指标卡重复）
def _render_weather_block():
    """天气展示 + 数据来源标识 + 阈值预警。"""
    weather_data = fetch_weather_data()
    now_weather = weather_data["now"]
    st.markdown(
        f"🌤️ **实时天气**：当前温度 `{now_weather['temp']} ℃` ｜ 相对湿度 `{now_weather['humidity']} %` "
        f"｜ 风速 `{now_weather['windSpeed']} km/h` ｜ 天气状况 `{now_weather['text']}`"
    )

    # 数据来源标识：接口失败时明确告知，避免把演示数据当成实时数据
    if weather_data.get("status") != "success":
        st.error(
            "⚠️ 当前天气为**演示数据**（随机生成），并非实时天气。"
            "原因：未读取到和风天气 API 密钥（Streamlit Secrets 缺少 QWEATHER_KEY，或密钥失效）。"
            "配置后刷新页面即可显示真实数据。"
        )

    # 扩展：天气阈值预警
    try:
        temp_val = float(now_weather["temp"])
        wind_val = float(now_weather["windSpeed"])
        if temp_val >= 33:
            st.warning(f"⚠️ 高温预警：当前 {temp_val}℃，注意防暑。")
        elif temp_val <= 5:
            st.warning(f"⚠️ 低温预警：当前 {temp_val}℃，注意保暖。")
        if wind_val >= 8:
            st.warning(f"⚠️ 大风预警：当前风速 {wind_val} km/h。")
    except (TypeError, ValueError):
        pass


@st.fragment(run_every=60)
def _render_weather_block_auto():
    """60 秒自动刷新的天气块（st.fragment 局部刷新，不阻塞整页）。"""
    _render_weather_block()


if auto_refresh:
    _render_weather_block_auto()
else:
    _render_weather_block()

st.divider()

# 8. 地图区
st.subheader("🗺️ 校园地图")

col_t1, col_t2, col_t3 = st.columns(3)
with col_t1:
    show_bus = st.checkbox("显示 5路公交", value=True)
with col_t2:
    show_shuttle = st.checkbox("显示 通勤车", value=True)
with col_t3:
    show_sightseeing = st.checkbox("显示 观光车呼叫点", value=True)

filtered_df = flow_df[flow_df["类型"].isin(picked_types)] if picked_types else flow_df.iloc[0:0]
filtered_df = filtered_df[
    (filtered_df["人流量"] >= flow_range[0]) & (filtered_df["人流量"] <= flow_range[1])
]
latest_df = latest_flow(filtered_df) if len(filtered_df) else filtered_df
buildings_df = with_coords(latest_df) if len(latest_df) else None

fig_map = render_map(show_bus, show_shuttle, show_sightseeing, is_dark=dark_mode, buildings=buildings_df)

map_data = st_folium(
    fig_map,
    width="100%",
    height=600,
    key="campus_map",
    returned_objects=["last_clicked"],
)

if map_data and map_data.get("last_clicked"):
    st.session_state.current_lat = map_data["last_clicked"]["lat"]
    st.session_state.current_lng = map_data["last_clicked"]["lng"]

if buildings_df is None or len(buildings_df) == 0:
    st.warning("当前筛选条件下没有可展示的建筑数据，请重新勾选建筑类型。")
else:
    st.caption("圆点大小代表人流量，颜色代表使用率：蓝 < 60% ≤ 橙 < 85% ≤ 红。")

st.divider()

# 9. 维度统计区 + 明细区
st.subheader("📊 数据分析图表")

if len(filtered_df) == 0:
    st.info("当前筛选条件下没有数据，请调整侧边栏的「建筑类型」或「人流量范围」。")
else:
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.markdown("##### 各类型人流量对比")
        st.plotly_chart(render_type_bar(filtered_df, is_dark=dark_mode), width="stretch")
    with row1_col2:
        st.markdown("##### 建筑人流量排行")
        st.plotly_chart(render_rank_bar(filtered_df, is_dark=dark_mode), width="stretch")

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.markdown("##### 校园人群活动结构")
        st.plotly_chart(render_pie_chart(filtered_df, is_dark=dark_mode), width="stretch")
    with row2_col2:
        st.markdown("##### 校园建筑明细")
        st.dataframe(render_table(filtered_df), width="stretch", height=350, hide_index=True)

    row3_col1, row3_col2 = st.columns(2)
    with row3_col1:
        st.markdown("##### 平均使用率仪表盘")
        st.plotly_chart(render_gauge(filtered_df, is_dark=dark_mode), width="stretch")
    with row3_col2:
        st.markdown("##### 未来24小时温度与降水趋势")
        st.plotly_chart(render_line_chart(is_dark=dark_mode), width="stretch")

    # 扩展：低使用率预警
    latest_warn = latest_flow(filtered_df)
    low_use = latest_warn[latest_warn["使用率(%)"] < 40]
    if len(low_use) > 0:
        names = "、".join(low_use["建筑名称"].tolist())
        st.warning(f"⚠️ 低使用率提醒：{names} 使用率低于 40%。")

st.divider()
st.caption("实验2 数据看板 | 数据源：清洗后的校园人流模拟数据集 + 和风天气 API（失败时自动降级为模拟数据）")
