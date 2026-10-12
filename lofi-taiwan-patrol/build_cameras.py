#!/usr/bin/env python3
"""
台灣慢電視漫遊者（Lo-Fi Taiwan Patrol）：鏡頭資料管線
把「縣市,點位名稱,原始串流影像網址,華興城觀看網址」CSV 轉成模組二規格的 cameras.json。

用法：
    python3 build_cameras.py data/cameras_source.csv -o cameras.json
    python3 build_cameras.py data/cameras_source.csv -o cameras.json --dedupe
    python3 build_cameras.py data/cameras_source.csv -o cameras.json --resolve-hls-pages

只用 Python 標準函式庫（3.9+），不需要 pip install。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# 1. 縣市正規化
# ---------------------------------------------------------------------------
COUNTY_RE = re.compile(r"^(..[市縣])(.*)$")

# 鏡頭面向判斷用：東部海岸看日出，西部海岸看夕陽
EAST_COAST = {"宜蘭縣", "花蓮縣", "臺東縣"}
WEST_COAST = {"桃園市", "臺中市", "嘉義縣", "臺南市", "高雄市", "澎湖縣", "金門縣", "連江縣"}
OUTLYING = {"澎湖縣", "金門縣", "連江縣"}


def normalize_county(raw: str) -> tuple[str, str]:
    """'台東縣' -> ('臺東縣', '')；'新北市新店區' -> ('新北市', '新店區')"""
    raw = raw.strip().replace("台", "臺")
    m = COUNTY_RE.match(raw)
    if not m:
        return raw, ""
    return m.group(1), m.group(2).strip()


# ---------------------------------------------------------------------------
# 2. 串流格式判斷
# ---------------------------------------------------------------------------
YT_ID_RE = re.compile(r"(?:v=|youtu\.be/|/live/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")


def detect_stream(url: str) -> dict:
    """回傳 type（yt|hls）與播放器需要的附加欄位。"""
    url = url.strip()
    host = urllib.parse.urlparse(url).hostname or ""
    if "youtube.com" in host or "youtu.be" in host:
        m = YT_ID_RE.search(url)
        if not m:
            raise ValueError(f"無法解析 YouTube 影片 ID：{url}")
        vid = m.group(1)
        return {
            "type": "yt",
            "stream_url": f"https://www.youtube.com/watch?v={vid}",
            "youtube_id": vid,
            "embed_url": (
                f"https://www.youtube-nocookie.com/embed/{vid}"
                "?autoplay=1&mute=1&controls=0&disablekb=1&modestbranding=1"
                "&rel=0&iv_load_policy=3&playsinline=1"
            ),
            "stream_host": host,
            "stream_kind": "youtube_live",
            "needs_resolve": False,
        }
    if urllib.parse.urlparse(url).path.endswith(".m3u8"):
        return {
            "type": "hls",
            "stream_url": url,
            "stream_host": host,
            "stream_kind": "m3u8",
            "needs_resolve": False,
        }
    # hls.bote.gov.taipei/live/index.html?id=NNN：是內嵌播放器的 HTML 頁，不是 m3u8
    return {
        "type": "hls",
        "stream_url": url,
        "stream_host": host,
        "stream_kind": "hls_player_page",
        "needs_resolve": True,
    }


M3U8_IN_HTML_RE = re.compile(r"""["'(]([^"'()\s]+?\.m3u8[^"'()\s]*)["')]""")


def resolve_player_page(url: str, timeout: float = 8.0) -> str | None:
    """抓播放器 HTML，從原始碼找出第一個 .m3u8 位址；找不到或連線失敗回傳 None。"""
    req = urllib.request.Request(url, headers={"User-Agent": "LoFiTaiwanPatrol/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(256_000).decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - 任何網路錯誤都視為無法解析
        print(f"  [resolve] {url} 失敗：{exc}", file=sys.stderr)
        return None
    m = M3U8_IN_HTML_RE.search(html)
    return urllib.parse.urljoin(url, m.group(1)) if m else None


# ---------------------------------------------------------------------------
# 3. 分類規則
#    判斷順序：人工覆寫 → 監控（HLS）→ 離島縣市 → 海 → 水岸 → 山 → 都市景點 → 預設
#    每台鏡頭都會寫入 classification.rule，方便人工抽查。
# ---------------------------------------------------------------------------

# 名稱裡沒有可靠關鍵字，或關鍵字會判錯的點位，直接指定 (category, subcategory)
MANUAL_OVERRIDES: dict[str, tuple[str, str]] = {
    # 有「湖、山、橋」，但其實是海岸景點
    "後壁湖": ("ocean", "harbor"),
    "大石鼻山": ("ocean", "coastal_headland"),
    "長虹橋": ("ocean", "coastal_bridge"),
    "金崙大橋": ("ocean", "coastal_bridge"),
    # 沒有關鍵字的海岸點位
    "台東多良車站": ("ocean", "coastal_railway"),
    "天堂路": ("ocean", "coastal_road"),
    "華源曙光觀景台": ("ocean", "sunrise_coast"),
    "台東華源曙光觀景台即時影像": ("ocean", "sunrise_coast"),
    "三仙台": ("ocean", "coastal_landmark"),
    "東海岸即時影像 - 三仙台": ("ocean", "coastal_landmark"),
    "石梯坪": ("ocean", "rocky_coast"),
    "金樽遊憩區": ("ocean", "beach"),
    "加路蘭遊憩區": ("ocean", "rocky_coast"),
    "都歷遊客中心": ("ocean", "coastal_viewpoint"),
    "鼻頭服務區": ("ocean", "coastal_viewpoint"),
    "馬崗哨所": ("ocean", "rocky_coast"),
    "合界": ("ocean", "rocky_coast"),
    "社皆坑": ("ocean", "rocky_coast"),
    "社皆坑海灣": ("ocean", "rocky_coast"),
    "萬里桐即時影像": ("ocean", "rocky_coast"),
    "旗津": ("ocean", "beach"),
    "老梅綠石槽即時影像": ("ocean", "rocky_coast"),
    "頭城合興里": ("ocean", "beach"),
    "舊草嶺自行車隧道(南口)": ("ocean", "coastal_viewpoint"),
    "花蓮海岸_忘憂亭": ("ocean", "coastal_viewpoint"),
    "海生館": ("ocean", "aquarium"),
    "七星潭_北埔安檢所，花蓮縣新城鄉": ("ocean", "beach"),  # 七星潭是礫石海灘，不是湖
    "基隆海洋廣場": ("ocean", "harbor"),
    # 有「港、島」，但其實是內陸水域
    "許厝港濕地": ("waterfront", "wetland"),
    "阿姆坪薑母島": ("waterfront", "reservoir"),
    "三龜戲水": ("waterfront", "river"),
    "官田遊客中心": ("waterfront", "wetland"),
    # 有「湖」，但其實是山區聚落
    "奮起湖": ("mountain", "mountain_village"),
    # 沒有關鍵字的山區點位
    "台中望高寮": ("mountain", "city_view_peak"),
    "烘爐地即時影像": ("mountain", "city_view_peak"),
    "劍潭山微風平台": ("mountain", "city_view_peak"),  # 名稱有「潭」，但是山
    "貓空指南宮": ("mountain", "city_view_peak"),
    "二寮觀日平臺": ("mountain", "badlands_sunrise"),
    "上巴陵": ("mountain", "mountain_village"),
    "里佳資訊站": ("mountain", "mountain_village"),
    "觸口遊客中心": ("mountain", "foothill"),
    "石桌即時影像": ("mountain", "tea_plantation"),
    "牛埔仔愛情大草原": ("mountain", "grassland"),
    "風箏坪": ("mountain", "grassland"),
    # 都市景點（不是監控，但屬於城市）
    "九份即時影像": ("city_traffic", "old_street"),
    "大溪老街": ("city_traffic", "old_street"),  # 名稱有「溪」，但是老街
    "桃園國際機場_大古山": ("city_traffic", "airport"),  # 從山上看機場跑道
    "天母棒球場": ("city_traffic", "stadium"),
    "高雄流行音樂中心": ("city_traffic", "urban_landmark"),
    "壽山動物園－狐獴展區": ("city_traffic", "zoo"),
}

# 名稱有這些字時，鏡頭以城市夜景為主，時段用 dusk/night
CITY_VIEW_PEAKS = ("象山看台北", "劍潭山", "碧山巖", "壽山情人觀景台", "虎頭山", "觀音山")

ISLAND_KW = ("島", "嶼", "綠島", "澎湖", "金門", "東引")
OCEAN_KW = (
    ("水下", "underwater"),
    ("海水浴場", "beach"), ("沙灘", "beach"), ("海灘", "beach"),
    ("漁港", "harbor"), ("港", "harbor"),
    ("海岸", "coastline"), ("濱海", "coastline"), ("海洋", "coastline"),
    ("灣", "bay"), ("浮潛", "reef"), ("海", "coastline"), ("潮境", "coastline"),
)
WATER_KW = (
    ("瀑布", "waterfall"), ("水庫", "reservoir"), ("濕地", "wetland"),
    ("吊橋", "river"), ("溪", "river"), ("河", "river"), ("左岸", "river"),
    ("渡船頭", "river"), ("碼頭", "river"),
    ("潭", "lake"), ("湖", "lake"), ("橋", "river"),
)
MOUNTAIN_KW = (
    ("森林遊樂區", "forest"), ("森林", "forest"), ("步道", "trail"),
    ("雲梯", "trail"), ("農場", "farm"), ("高台", "plateau"),
    ("嶺", "peak"), ("啞口", "pass"), ("山", "peak"), ("砲台", "peak"),
)
CITY_KW = (("機場", "airport"), ("老街", "old_street"), ("車站", "station"))

# 臺北、新北 HLS 監控的細分類
TRAFFIC_MOUNTAIN_ROAD_KW = ("竹子湖", "陽金", "仰德")
TRAFFIC_SUB_KW = (
    ("隧道", "tunnel"),
    ("頂樓", "rooftop"),
    ("門架", "expressway"), ("高架", "expressway"), ("市高", "expressway"),
    ("交流道", "expressway"), ("匝道", "expressway"), ("快", "expressway"),
    ("新生高", "expressway"),
    ("台2線", "provincial_highway"),
    ("橋", "bridge"),
)


def _first_kw(name: str, table) -> str | None:
    for kw, sub in table:
        if kw in name:
            return sub
    return None


def classify(name: str, county: str, stream: dict) -> dict:
    clean = re.sub(r"^[^\w一-鿿]+", "", name).strip()  # 去掉開頭的 🔴

    if clean in MANUAL_OVERRIDES:
        cat, sub = MANUAL_OVERRIDES[clean]
        return {"category": cat, "subcategory": sub, "rule": "manual_override", "needs_review": False}

    if stream["type"] == "hls":
        if any(k in clean for k in TRAFFIC_MOUNTAIN_ROAD_KW):
            return {"category": "mountain", "subcategory": "mountain_road", "rule": "hls_mountain_road", "needs_review": False}
        sub = _first_kw(clean, TRAFFIC_SUB_KW) or "intersection"
        return {"category": "city_traffic", "subcategory": sub, "rule": "hls_traffic", "needs_review": False}

    if county in OUTLYING or any(k in clean for k in ISLAND_KW):
        sub = _first_kw(clean, OCEAN_KW) or "island_coast"
        return {"category": "island", "subcategory": sub, "rule": "island", "needs_review": False}

    for cat, table, rule in (
        ("ocean", OCEAN_KW, "kw_ocean"),
        ("waterfront", WATER_KW, "kw_water"),
        ("mountain", MOUNTAIN_KW, "kw_mountain"),
        ("city_traffic", CITY_KW, "kw_city"),
    ):
        sub = _first_kw(clean, table)
        if sub:
            if cat == "mountain" and any(k in clean for k in CITY_VIEW_PEAKS):
                sub = "city_view_peak"
            return {"category": cat, "subcategory": sub, "rule": rule, "needs_review": False}

    # 沒有任何規則命中：YouTube 觀光直播多半在郊外，先歸山區並標記待人工確認
    return {"category": "mountain", "subcategory": "unknown", "rule": "fallback", "needs_review": True}


# ---------------------------------------------------------------------------
# 4. 時段適配（dawn 05-08 / day 08-17 / dusk 17-19 / night 19-05）
#    原則：沒有路燈的自然景觀晚上一片黑，不排 night；有燈的城市才排 night。
# ---------------------------------------------------------------------------
def time_suitability(cat: str, sub: str, county: str, name: str) -> list[str]:
    if cat == "city_traffic":
        if sub == "tunnel":
            return ["all"]  # 隧道照明恆定，任何時段畫面都一樣
        if sub in ("old_street", "stadium", "zoo", "station"):
            return ["day", "dusk"]
        if sub == "airport":
            return ["day", "dusk", "night"]
        return ["dusk", "night"]  # 車燈光軌是深夜慢電視的主角
    if sub == "city_view_peak":
        return ["dusk", "night"]
    if sub == "underwater" or sub == "aquarium":
        return ["day"]
    if any(k in name for k in ("曙光", "觀日", "日出")) or sub in ("sunrise_coast", "badlands_sunrise"):
        return ["dawn", "day"]
    if cat in ("ocean", "island"):
        if county in EAST_COAST:
            return ["dawn", "day"]
        if county in WEST_COAST or any(k in name for k in ("淡水", "八里", "夕陽")):
            return ["day", "dusk"]
        return ["dawn", "day", "dusk"] if cat == "island" else ["day", "dusk"]
    if cat == "mountain":
        if sub == "mountain_road":
            return ["day", "dusk", "night"]
        return ["dawn", "day"]  # 雲海、晨霧
    if cat == "waterfront":
        return ["day", "dusk"]
    return ["day"]


# ---------------------------------------------------------------------------
# 5. 環境音設定檔（給模組四 Track 2 使用）
#    gain 是線性音量 0~1；lowpass_hz 是該層的低通截止頻率；
#    night_swap 是夜間（19:00-05:00）要換掉的素材。
# ---------------------------------------------------------------------------
AMBIENT_PROFILES: dict[str, dict] = {
    "ocean_waves": {
        "label": "浪濤與海風",
        "layers": [
            {"asset": "sfx/waves_gentle_loop.ogg", "gain": 0.70, "lowpass_hz": 6000},
            {"asset": "sfx/sea_breeze_loop.ogg", "gain": 0.30, "lowpass_hz": 3000},
            {"asset": "sfx/seagull_oneshots.ogg", "gain": 0.12, "random_interval_s": [25, 90]},
        ],
        "night_swap": {"sfx/seagull_oneshots.ogg": None},
    },
    "harbor_dock": {
        "label": "漁港船聲",
        "layers": [
            {"asset": "sfx/harbor_lapping_loop.ogg", "gain": 0.55, "lowpass_hz": 5000},
            {"asset": "sfx/boat_rope_creak_loop.ogg", "gain": 0.25, "lowpass_hz": 4000},
            {"asset": "sfx/boat_engine_far_oneshots.ogg", "gain": 0.15, "random_interval_s": [60, 180]},
        ],
        "night_swap": {"sfx/boat_engine_far_oneshots.ogg": None},
    },
    "rocky_shore": {
        "label": "礁岸拍浪",
        "layers": [
            {"asset": "sfx/waves_rock_crash_loop.ogg", "gain": 0.65, "lowpass_hz": 7000},
            {"asset": "sfx/sea_breeze_loop.ogg", "gain": 0.35, "lowpass_hz": 3000},
        ],
        "night_swap": {},
    },
    "underwater_bubbles": {
        "label": "水下氣泡",
        "layers": [
            {"asset": "sfx/underwater_hum_loop.ogg", "gain": 0.60, "lowpass_hz": 800},
            {"asset": "sfx/bubbles_oneshots.ogg", "gain": 0.20, "random_interval_s": [4, 15]},
        ],
        "night_swap": {},
    },
    "island_breeze": {
        "label": "離島風聲",
        "layers": [
            {"asset": "sfx/strong_wind_grass_loop.ogg", "gain": 0.50, "lowpass_hz": 4000},
            {"asset": "sfx/waves_far_loop.ogg", "gain": 0.40, "lowpass_hz": 2500},
            {"asset": "sfx/seagull_oneshots.ogg", "gain": 0.10, "random_interval_s": [40, 120]},
        ],
        "night_swap": {"sfx/seagull_oneshots.ogg": None},
    },
    "river_flow": {
        "label": "溪流潺潺",
        "layers": [
            {"asset": "sfx/stream_flow_loop.ogg", "gain": 0.60, "lowpass_hz": 8000},
            {"asset": "sfx/birds_riverside_loop.ogg", "gain": 0.20},
        ],
        "night_swap": {"sfx/birds_riverside_loop.ogg": "sfx/frogs_loop.ogg"},
    },
    "waterfall": {
        "label": "瀑布白噪音",
        "layers": [
            {"asset": "sfx/waterfall_loop.ogg", "gain": 0.75, "lowpass_hz": 5000},
            {"asset": "sfx/forest_birds_loop.ogg", "gain": 0.15},
        ],
        "night_swap": {"sfx/forest_birds_loop.ogg": None},
    },
    "lake_calm": {
        "label": "湖面微風",
        "layers": [
            {"asset": "sfx/lake_ripple_loop.ogg", "gain": 0.45, "lowpass_hz": 4000},
            {"asset": "sfx/soft_wind_loop.ogg", "gain": 0.25, "lowpass_hz": 2500},
            {"asset": "sfx/birds_riverside_loop.ogg", "gain": 0.20},
        ],
        "night_swap": {"sfx/birds_riverside_loop.ogg": "sfx/frogs_loop.ogg"},
    },
    "wetland_birds": {
        "label": "濕地水鳥",
        "layers": [
            {"asset": "sfx/wetland_reeds_wind_loop.ogg", "gain": 0.40, "lowpass_hz": 4000},
            {"asset": "sfx/egret_heron_oneshots.ogg", "gain": 0.18, "random_interval_s": [20, 70]},
            {"asset": "sfx/frogs_loop.ogg", "gain": 0.10},
        ],
        "night_swap": {"sfx/egret_heron_oneshots.ogg": None},
    },
    "mountain_wind_insects": {
        "label": "山風與蟲鳴",
        "layers": [
            {"asset": "sfx/mountain_wind_loop.ogg", "gain": 0.45, "lowpass_hz": 3000},
            {"asset": "sfx/cicadas_loop.ogg", "gain": 0.30, "lowpass_hz": 9000},
            {"asset": "sfx/forest_birds_loop.ogg", "gain": 0.20},
        ],
        "night_swap": {"sfx/cicadas_loop.ogg": "sfx/crickets_loop.ogg", "sfx/forest_birds_loop.ogg": None},
    },
    "forest_canopy": {
        "label": "森林樹冠",
        "layers": [
            {"asset": "sfx/forest_leaves_rustle_loop.ogg", "gain": 0.45, "lowpass_hz": 6000},
            {"asset": "sfx/forest_birds_loop.ogg", "gain": 0.35},
            {"asset": "sfx/distant_stream_loop.ogg", "gain": 0.15, "lowpass_hz": 3000},
        ],
        "night_swap": {"sfx/forest_birds_loop.ogg": "sfx/owl_crickets_loop.ogg"},
    },
    "alpine_wind": {
        "label": "高山強風",
        "layers": [
            {"asset": "sfx/alpine_wind_gust_loop.ogg", "gain": 0.60, "lowpass_hz": 2500},
            {"asset": "sfx/flag_flap_loop.ogg", "gain": 0.10},
        ],
        "night_swap": {},
    },
    "city_night_view": {
        "label": "山上看城市",
        "layers": [
            {"asset": "sfx/soft_wind_loop.ogg", "gain": 0.35, "lowpass_hz": 2500},
            {"asset": "sfx/city_far_rumble_loop.ogg", "gain": 0.30, "lowpass_hz": 400},
            {"asset": "sfx/cicadas_loop.ogg", "gain": 0.15},
        ],
        "night_swap": {"sfx/cicadas_loop.ogg": "sfx/crickets_loop.ogg"},
    },
    "highway_hum": {
        "label": "高架車流嗡鳴",
        "layers": [
            {"asset": "sfx/highway_drone_loop.ogg", "gain": 0.55, "lowpass_hz": 350},
            {"asset": "sfx/car_pass_by_oneshots.ogg", "gain": 0.15, "lowpass_hz": 1200, "random_interval_s": [3, 12]},
        ],
        "night_swap": {},
    },
    "tunnel_drone": {
        "label": "隧道低頻共鳴",
        "layers": [
            {"asset": "sfx/tunnel_fan_drone_loop.ogg", "gain": 0.50, "lowpass_hz": 250},
            {"asset": "sfx/car_pass_tunnel_oneshots.ogg", "gain": 0.20, "lowpass_hz": 900, "random_interval_s": [4, 15]},
        ],
        "night_swap": {},
    },
    "city_intersection": {
        "label": "路口機車與行人號誌",
        "layers": [
            {"asset": "sfx/city_traffic_mid_loop.ogg", "gain": 0.45, "lowpass_hz": 1500},
            {"asset": "sfx/scooter_pass_oneshots.ogg", "gain": 0.18, "lowpass_hz": 2500, "random_interval_s": [5, 20]},
            {"asset": "sfx/tw_crosswalk_bird_beep.ogg", "gain": 0.06, "random_interval_s": [90, 150]},
        ],
        "night_swap": {"sfx/scooter_pass_oneshots.ogg": None},
    },
    "rooftop_city": {
        "label": "頂樓遠方城市",
        "layers": [
            {"asset": "sfx/city_far_rumble_loop.ogg", "gain": 0.40, "lowpass_hz": 500},
            {"asset": "sfx/rooftop_wind_loop.ogg", "gain": 0.30, "lowpass_hz": 2000},
            {"asset": "sfx/ac_unit_hum_loop.ogg", "gain": 0.08, "lowpass_hz": 300},
        ],
        "night_swap": {},
    },
    "airport_apron": {
        "label": "跑道噴射機",
        "layers": [
            {"asset": "sfx/airport_ambience_loop.ogg", "gain": 0.40, "lowpass_hz": 1200},
            {"asset": "sfx/jet_takeoff_far_oneshots.ogg", "gain": 0.25, "lowpass_hz": 1500, "random_interval_s": [120, 300]},
        ],
        "night_swap": {},
    },
    "old_street_crowd": {
        "label": "老街人聲",
        "layers": [
            {"asset": "sfx/market_crowd_murmur_loop.ogg", "gain": 0.40, "lowpass_hz": 2000},
            {"asset": "sfx/wind_chime_oneshots.ogg", "gain": 0.10, "random_interval_s": [30, 90]},
        ],
        "night_swap": {},
    },
    "railway_rural": {
        "label": "鄉間小站",
        "layers": [
            {"asset": "sfx/cicadas_loop.ogg", "gain": 0.30},
            {"asset": "sfx/train_pass_far_oneshots.ogg", "gain": 0.25, "lowpass_hz": 2000, "random_interval_s": [600, 1200]},
            {"asset": "sfx/waves_far_loop.ogg", "gain": 0.25, "lowpass_hz": 2500},
        ],
        "night_swap": {"sfx/cicadas_loop.ogg": "sfx/crickets_loop.ogg"},
    },
}

SUB_TO_PROFILE = {
    # ocean / island
    "harbor": "harbor_dock", "underwater": "underwater_bubbles", "aquarium": "underwater_bubbles",
    "reef": "rocky_shore", "rocky_coast": "rocky_shore", "coastal_headland": "rocky_shore",
    "coastal_railway": "railway_rural",
    # waterfront
    "river": "river_flow", "waterfall": "waterfall", "lake": "lake_calm",
    "reservoir": "lake_calm", "wetland": "wetland_birds",
    # mountain
    "forest": "forest_canopy", "trail": "forest_canopy", "pass": "alpine_wind",
    "city_view_peak": "city_night_view", "mountain_road": "mountain_wind_insects",
    # city
    "tunnel": "tunnel_drone", "expressway": "highway_hum", "provincial_highway": "highway_hum",
    "bridge": "highway_hum", "rooftop": "rooftop_city", "intersection": "city_intersection",
    "airport": "airport_apron", "old_street": "old_street_crowd", "station": "railway_rural",
    "stadium": "old_street_crowd", "zoo": "old_street_crowd", "urban_landmark": "rooftop_city",
}
CATEGORY_DEFAULT_PROFILE = {
    "ocean": "ocean_waves", "island": "island_breeze", "waterfront": "river_flow",
    "mountain": "mountain_wind_insects", "city_traffic": "city_intersection",
}
HIGH_ALTITUDE_KW = ("合歡山", "武嶺", "南橫", "太平山", "阿里山", "拉拉山")


def ambient_profile(cat: str, sub: str, name: str) -> str:
    if cat == "mountain" and any(k in name for k in HIGH_ALTITUDE_KW):
        return "alpine_wind" if ("武嶺" in name or "啞口" in name) else "forest_canopy"
    if cat == "island" and sub not in ("harbor", "underwater", "reef"):
        return "island_breeze"
    return SUB_TO_PROFILE.get(sub, CATEGORY_DEFAULT_PROFILE[cat])


# ---------------------------------------------------------------------------
# 6. 斷流時的視覺降級畫面，依分類挑最搭的預錄素材
# ---------------------------------------------------------------------------
FALLBACK_VISUAL = {
    "ocean": "loop/rain_window_seaside.webm",
    "island": "loop/rain_window_seaside.webm",
    "waterfront": "loop/rain_window_river.webm",
    "mountain": "loop/foggy_window_mountain.webm",
    "city_traffic": "loop/vhs_maintenance_city.webm",
}

# 依串流類型的健康檢查參數（模組二 Failover Pipeline）
HEALTH_POLICY = {
    "yt": {
        "probe": "oembed",  # GET https://www.youtube.com/oembed?url=...，200=影片存在
        "probe_interval_s": 300,
        "timeout_ms": 6000,
        "player_stall_timeout_ms": 15000,  # IFrame 播放器 BUFFERING 超過 15 秒視為斷流
        "retry_backoff_ms": [2000, 5000, 15000, 60000],
        "max_retries": 4,
        "cooldown_after_fail_s": 1800,
    },
    "hls": {
        "probe": "manifest_get",  # GET m3u8，需 200 且含 #EXTM3U
        "probe_interval_s": 60,
        "timeout_ms": 4000,
        "player_stall_timeout_ms": 8000,  # hls.js 連續 8 秒沒有新片段
        "retry_backoff_ms": [1000, 3000, 8000, 20000],
        "max_retries": 4,
        "cooldown_after_fail_s": 600,
    },
}


# ---------------------------------------------------------------------------
# 7. 主流程
# ---------------------------------------------------------------------------
REQUIRED_COLS = ("縣市", "點位名稱", "原始串流影像網址")


def make_id(stream: dict, watch_url: str, row_no: int) -> str:
    """穩定 ID：優先用華興城 watch 參數（全表唯一），其次用串流網址雜湊。"""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(watch_url).query).get("watch", [""])[0]
    key = q or hashlib.sha1(stream["stream_url"].encode()).hexdigest()[:16]
    return f"{stream['type']}-{key}" if key else f"{stream['type']}-row{row_no:04d}"


def build(rows: list[dict], dedupe: bool, resolve_pages: bool) -> tuple[list[dict], list[str]]:
    cameras: list[dict] = []
    warnings: list[str] = []
    seen_url: dict[str, str] = {}

    for i, row in enumerate(rows, start=2):  # 第 1 列是標題
        name = (row.get("點位名稱") or "").strip()
        url = (row.get("原始串流影像網址") or "").strip()
        if not name or not url:
            warnings.append(f"第 {i} 列缺少名稱或網址，略過")
            continue
        try:
            stream = detect_stream(url)
        except ValueError as exc:
            warnings.append(f"第 {i} 列：{exc}")
            continue

        if stream["needs_resolve"] and resolve_pages:
            m3u8 = resolve_player_page(stream["stream_url"])
            if m3u8:
                stream.update(stream_url=m3u8, stream_kind="m3u8", needs_resolve=False, player_page_url=url)

        county, district = normalize_county(row.get("縣市", ""))
        cls = classify(name, county, stream)
        cat, sub = cls["category"], cls["subcategory"]
        cam_id = make_id(stream, row.get("華興城觀看網址", ""), i)

        dup_of = seen_url.get(stream["stream_url"])
        if dup_of and dedupe:
            warnings.append(f"第 {i} 列「{name}」與 {dup_of} 串流相同，已移除")
            continue
        seen_url.setdefault(stream["stream_url"], cam_id)

        cam = {
            "id": cam_id,
            "name": name.lstrip("🔴 ").strip(),
            "type": stream["type"],
            "stream_url": stream["stream_url"],
            "category": cat,
            "subcategory": sub,
            "time_suitability": time_suitability(cat, sub, county, name),
            "ambient_sound_profile": ambient_profile(cat, sub, name),
            "region": {"county": county, "district": district or None},
            "source": {
                "watch_page": row.get("華興城觀看網址", "").strip() or None,
                "stream_host": stream["stream_host"],
                "stream_kind": stream["stream_kind"],
            },
            "player": {
                "needs_resolve": stream["needs_resolve"],
                "has_live_audio": stream["type"] == "yt",  # 政府 CCTV 一律無收音
                "live_audio_default_gain": 0.25 if stream["type"] == "yt" else 0.0,
            },
            "fallback_visual": FALLBACK_VISUAL[cat],
            "classification": {"rule": cls["rule"], "needs_review": cls["needs_review"]},
            "duplicate_of": dup_of,
        }
        if stream["type"] == "yt":
            cam["player"]["youtube_id"] = stream["youtube_id"]
            cam["player"]["embed_url"] = stream["embed_url"]
        if "player_page_url" in stream:
            cam["source"]["player_page_url"] = stream["player_page_url"]
        if cls["needs_review"]:
            warnings.append(f"「{name}」沒有命中任何分類規則，暫列 mountain，請人工確認")
        cameras.append(cam)

    return cameras, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CSV → cameras.json（Lo-Fi Taiwan Patrol 模組二）")
    ap.add_argument("csv_path")
    ap.add_argument("-o", "--output", default="cameras.json")
    ap.add_argument("--dedupe", action="store_true", help="串流網址重複的點位只留第一筆")
    ap.add_argument("--resolve-hls-pages", action="store_true",
                    help="連線抓 hls.bote.gov.taipei 播放器頁，嘗試取出真正的 .m3u8")
    ap.add_argument("--strict", action="store_true", help="有任何警告就以結束碼 1 結束")
    args = ap.parse_args(argv)

    with open(args.csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLS if c not in (reader.fieldnames or [])]
        if missing:
            print(f"CSV 缺少欄位：{missing}", file=sys.stderr)
            return 2
        rows = list(reader)

    cameras, warnings = build(rows, args.dedupe, args.resolve_hls_pages)

    stats = {
        "total": len(cameras),
        "by_type": dict(Counter(c["type"] for c in cameras)),
        "by_category": dict(Counter(c["category"] for c in cameras)),
        "by_ambient_profile": dict(Counter(c["ambient_sound_profile"] for c in cameras)),
        "needs_resolve": sum(c["player"]["needs_resolve"] for c in cameras),
        "needs_review": sum(c["classification"]["needs_review"] for c in cameras),
        "duplicates": sum(1 for c in cameras if c["duplicate_of"]),
    }
    doc = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_csv_rows": len(rows),
        "time_slots": {
            "dawn": "05:00-08:00", "day": "08:00-17:00",
            "dusk": "17:00-19:00", "night": "19:00-05:00",
        },
        "health_policy": HEALTH_POLICY,
        "ambient_profiles": AMBIENT_PROFILES,
        "stats": stats,
        "cameras": cameras,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"寫入 {args.output}：{stats['total']} 台鏡頭（CSV {len(rows)} 列）")
    print(f"  類型　　：{stats['by_type']}")
    print(f"  分類　　：{stats['by_category']}")
    print(f"  待解析 m3u8：{stats['needs_resolve']}　待人工確認：{stats['needs_review']}　重複：{stats['duplicates']}")
    for w in warnings:
        print(f"  ⚠ {w}", file=sys.stderr)
    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
