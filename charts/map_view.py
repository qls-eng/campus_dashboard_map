# charts/map_view.py
import folium
from data.mock import get_bus_stops, get_bus_route_from_amap, get_sightseeing_stops, get_staff_shuttle


def render_map(show_bus=True, show_shuttle=True, show_sightseeing=True, is_dark=False, buildings=None):
    """渲染校园地图。

    参数 buildings 传入带经纬度的建筑数据（含 建筑名称 / 类型 / 人流量 / 使用率(%)），
    不为空时按人流量大小绘制圆形点位，使地图与图表使用同一份清洗后数据。
    """
    df_bus = get_bus_stops()
    df_sightseeing = get_sightseeing_stops()
    df_staff = get_staff_shuttle()

    center_lat, center_lng = 25.0635, 110.2990
    tiles_url = "https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"

    m = folium.Map(location=[center_lat, center_lng], zoom_start=15, tiles=tiles_url, attr="高德地图")

    # ==========================================
    # 0. 建筑人流量点位（圆点大小随人流量变化）
    # ==========================================
    if buildings is not None and len(buildings) > 0:
        import math

        max_flow = max(int(buildings["人流量"].max()), 1)
        for _, row in buildings.iterrows():
            # 半径按人流量的平方根缩放，避免大值把地图糊住
            radius = 6 + 14 * math.sqrt(int(row["人流量"]) / max_flow)
            color = "#e45756" if row["使用率(%)"] >= 85 else ("#f2a541" if row["使用率(%)"] >= 60 else "#4c78a8")
            popup_html = f"""
            <div style="font-family: 'Microsoft YaHei', sans-serif; width: 200px;">
                <h4 style="margin: 0 0 5px 0;">{row['建筑名称']}</h4>
                <p style="margin: 0; font-size: 12px;">类型：{row['类型']}</p>
                <p style="margin: 0; font-size: 12px;">人流量：{int(row['人流量'])} 人次</p>
                <p style="margin: 0; font-size: 12px;">使用率：{row['使用率(%)']}%</p>
            </div>
            """
            folium.CircleMarker(
                location=[row["纬度"], row["经度"]],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.55,
                weight=1,
                tooltip=f"{row['建筑名称']}：{int(row['人流量'])} 人次",
                popup=folium.Popup(popup_html, max_width=250),
            ).add_to(m)

    # ==========================================
    # 1. 绘制 5路公交（手工平滑拐点，贴合真实站点、无绕路岔路）
    # ==========================================
    if show_bus:
        # 高德驾车路径规划 API：贴合真实道路、平滑；API 内部已做岔路裁剪
        bus_coords = get_bus_route_from_amap()
        if not bus_coords:
            # API 失败时退回手工拐点
            bus_coords = df_bus[["纬度", "经度"]].values.tolist()

        # 画橘色线
        folium.PolyLine(
            bus_coords, color="#ff7f0e", weight=6, opacity=0.9, tooltip="5路公交路线"
        ).add_to(m)

        # 画 5 个公交站点的图标（遍历时过滤掉隐藏的空站名）
        for _, row in df_bus.iterrows():
            if row["站点"] == "":
                continue # 遇到隐藏点直接跳过，不画图标

            popup_html = f"""
            <div style="font-family: 'Microsoft YaHei', sans-serif; width: 200px;">
                <h4 style="color: #ff7f0e; margin: 0 0 5px 0;">🚌 {row['站点']}</h4>
                <p style="margin: 0; font-size: 12px;">运营线路：5路公交</p>
                <p style="margin: 0; font-size: 12px;">首末班：06:50 - 21:00</p>
            </div>
            """
            folium.Marker(
                location=[row["纬度"], row["经度"]],
                icon=folium.Icon(color="orange", icon="bus", prefix="fa"),
                tooltip=f"点击查看：{row['站点']}详情",
                popup=folium.Popup(popup_html, max_width=250)
            ).add_to(m)

    # ==========================================
    # 2. 绘制观光车呼叫点
    # ==========================================
    if show_sightseeing:
        for _, row in df_sightseeing.iterrows():
            popup_html = f"""
            <div style="font-family: 'Microsoft YaHei', sans-serif; width: 200px;">
                <h4 style="color: #2ca02c; margin: 0 0 5px 0;">🚐 {row['名称']}（观光车）</h4>
                <p style="margin: 0; font-size: 12px;">运营模式：招手即停 / 小程序呼叫</p>
            </div>
            """
            folium.Marker(
                location=[row["纬度"], row["经度"]],
                icon=folium.Icon(color="green", icon="shuttle-van", prefix="fa"),
                tooltip=f"点击查看：{row['名称']}观光车信息",
                popup=folium.Popup(popup_html, max_width=250)
            ).add_to(m)

    # ==========================================
    # 3. 绘制教职工通勤车（最后绘制=最上层，不被观光车遮挡）
    # ==========================================
    if show_shuttle:
        for _, row in df_staff.iterrows():
            kind = row.get("乘车对象", "教职工")
            if kind == "学生":
                # 学生候车点：南门口，现场有余位即可上车，无官方固定班次
                popup_html = f"""
                <div style="font-family: 'Microsoft YaHei', sans-serif; width: 250px;">
                    <h4 style="color: #9467bd; margin: 0 0 6px 0;">🚌 {row['名称']}（通勤车）</h4>
                    <p style="margin: 0 0 6px 0; font-size: 12px;">运行区间：屏风校区 ↔ 雁山校区</p>
                    <div style="background: #f3f0fa; border-radius: 6px; padding: 8px;">
                        <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: bold; color:#5b3fa8;">🎓 学生候车说明</p>
                        <p style="margin: 0; font-size: 11px; line-height: 1.6;">
                            位置：南门口（校门内侧）<br>
                            乘车方式：有余位即可上车，无固定班次
                        </p>
                    </div>
                    <p style="margin: 6px 0 0 0; font-size: 11px; color:#888;">ℹ️「无固定班次」为现场观察，非学校官方规定；教职工班车时刻见教四楼 / 行知楼发车点。</p>
                </div>
                """
                # 紫色虚线空心圆 + "学生"字样，并置顶显示，避免被公交/观光车图标压住
                folium.Marker(
                    location=[row["纬度"], row["经度"]],
                    zIndexOffset=1000,
                    icon=folium.DivIcon(
                        html='<div style="width:40px;height:40px;line-height:34px;text-align:center;'
                             'font-size:12px;font-weight:bold;background:rgba(255,255,255,.95);color:#5b3fa8;'
                             'border:3px dashed #7b3ff2;border-radius:50%;box-shadow:0 2px 6px rgba(0,0,0,.25);">学生</div>',
                        icon_size=(40, 40),
                        icon_anchor=(20, 20),
                    ),
                    tooltip="点击查看：南门口学生候车点说明",
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(m)
            else:
                popup_html = f"""
                <div style="font-family: 'Microsoft YaHei', sans-serif; width: 250px;">
                    <h4 style="color: #9467bd; margin: 0 0 6px 0;">🚌 {row['名称']}（通勤车）</h4>
                    <p style="margin: 0 0 6px 0; font-size: 12px;">运行区间：屏风校区 ↔ 雁山校区</p>
                    <div style="background: #f3f0fa; border-radius: 6px; padding: 8px;">
                        <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: bold; color:#5b3fa8;">📅 雁山 → 屏风（发车时间）</p>
                        <p style="margin: 0; font-size: 11px; line-height: 1.6;">
                            教四楼：10:20　12:15<br>　　　　16:20　17:10　18:20　22:00<br>
                            行知楼：17:20
                        </p>
                    </div>
                    <div style="background: #f3f0fa; border-radius: 6px; padding: 8px; margin-top:6px;">
                        <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: bold; color:#5b3fa8;">📅 屏风 → 雁山（发车时间）</p>
                        <p style="margin: 0; font-size: 11px; line-height: 1.6;">
                            东城小区：7:20　8:00<br>
                            国际教育园区1号楼：7:20　8:05　9:15<br>　　　　　　　　13:20　15:05　20:30
                        </p>
                    </div>
                    <p style="margin: 6px 0 0 0; font-size: 11px; color:#888;">💳 教职工刷卡乘车，点对点直达，约 40 分钟</p>
                </div>
                """
                # 大号紫色自定义图标，确保视觉上不被观光车绿标盖住
                folium.Marker(
                    location=[row["纬度"], row["经度"]],
                    icon=folium.DivIcon(
                        html='<div style="width:44px;height:44px;line-height:44px;text-align:center;'
                             'font-size:26px;background:#7b3ff2;color:#fff;border-radius:50%;'
                             'border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,.4);">🚌</div>',
                        icon_size=(44, 44),
                        icon_anchor=(22, 44),
                    ),
                    tooltip=f"点击查看：{row['名称']}通勤车时刻表",
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(m)

    return m