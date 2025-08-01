import os
from flask import Flask, request, abort, render_template_string
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
from datetime import datetime, timedelta
import logging
import urllib3

# 設置日誌，方便除錯
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 禁用 SSL 警告，以解決部署環境的憑證驗證問題
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# --- 常數設定 (建議使用環境變數) ---
# LINE 憑證
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "voGLDMSHC/Xfng1zq62Tn4pGDC2ZWwb7l+HrUj54NNqXy1SfAy3Bs/EKp64WLlwQaSQeomnS1JmIWCqugoovc9IxNQfp8vA1PNdxUpYanXVh/vEGAKb4yrufufYMhp+kGsT4fUx+I+HwNIzHTqqtbgdB04t89/1O/w1cDnyilFU=")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "6362b12e044b913859b3772bf42cfa0d")
TO_USER_ID = os.getenv("TO_USER_ID", "Uaaec86d0060844844df5bb2e731a375f") # 啟動時推播訊息的 ID

# 氣象署金鑰
CWA_API_KEY = os.getenv("CWA_API_KEY", "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71")

# 口湖鄉潮汐預報 ID
KOUHU_TIDE_LOCATION_ID = "10009190"

# 天氣圖示對應
ICON_MAP = {
    '晴': '☀️', '多雲': '⛅', '陰': '☁️',
    '短暫雨': '🌧️', '陣雨': '🌦️', '雷陣雨': '⛈️',
    '雨': '🌧️', '局部雨': '🌦️',
    '雷': '⚡', '有霧': '🌫️', '降雪': '❄️',
    '冰雹': '🧊', '霾': '😷',
    '多雲時晴': '⛅', '晴時多雲': '⛅', '陰時多雲': '☁️'
}

# 常用連結清單
LINKS = [
    ("韌性防災", "https://yliflood.yunlin.gov.tw/cameralist/"),
    ("雲林路燈", "https://lamp.yunlin.gov.tw/slyunlin/Default.aspx"),
    ("管線挖掘", "https://pwd.yunlin.gov.tw/YLPub/"),
    ("台灣電力", "https://service.taipower.com.tw/nds/ndsWeb/ndft112.aspx"),
    ("停電查詢", "https://service.taipower.com.tw/branch/d120/xcnotice?xsmsid=0M242581310910082112"),
    ("自來水公司", "https://wateroff.water.gov.tw/"),
    ("氣象署資訊", "https://www.cwa.gov.tw/V8/C/"),
    ("停班課查詢", "https://www.dgpa.gov.tw/typh/daily/nds.html"),
]

# 機器人初始化
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- Flask 路由與主要處理邏輯 ---
@app.route("/")
def home():
    """首頁：顯示啟動狀態並推播訊息"""
    if TO_USER_ID:
        try:
            line_bot_api.push_message(
                TO_USER_ID,
                TextSendMessage(text="✅ LINE BOT 已啟動，請輸入：幫助")
            )
        except LineBotApiError as e:
            # 捕獲 LINE API 的特定錯誤，避免程式中斷
            logging.error(f"❌ 推播失敗：{e}")
        except Exception as e:
            # 捕獲其他未知錯誤
            logging.error(f"❌ 推播發生未知錯誤：{e}")
            
    html = """
    <h2>✅ LINE BOT 已啟動</h2>
    <p>輸入：「幫助」查看可用指令</p>
    <hr>
    <h3>🔗 常用連結</h3>
    <ul>
        {% for name, url in links %}
        <li><a href="{{ url }}" target="_blank">{{ name }}</a></li>
        {% endfor %}
    </ul>
    """
    return render_template_string(html, links=LINKS)

@app.route("/webhook", methods=['POST'])
def webhook():
    """LINE webhook 接收點，處理所有傳入的訊息"""
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logging.error("❌ 無效的簽章。請檢查您的 Channel Secret。")
        abort(400)
    except Exception as e:
        logging.error(f"❌ 處理 webhook 時發生錯誤：{e}")
        abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """根據使用者輸入的文字訊息進行回覆"""
    msg = event.message.text.strip().lower() # 將輸入轉為小寫，方便比對
    user_id = event.source.user_id

    # 使用字典對應指令，增加可讀性與擴充性
    commands = {
        "id": lambda: f"你的 LINE 使用者 ID 是：\n{user_id}",
        "天氣": get_weather_kouhu,
        "口湖天氣": get_weather_kouhu,
        "潮汐": get_tide_kouhu,
        "颱風": get_typhoon,
        "地震": get_earthquake,
        "連結": get_links_message,
        "幫助": lambda: "可用指令：\n天氣, 潮汐, 颱風, 地震, 連結"
    }
    
    # 這裡修改了預設回覆的邏輯
    res = commands.get(msg, lambda: "請輸入 **幫助** 來查看可用指令。")()
    
    if len(res) > 2000:
        res = res[:1990] + "..."
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

# --- API 取得資料函數區 ---
def get_weather_kouhu():
    """獲取口湖鄉 36 小時天氣預報"""
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}&locationName=雲林縣"
        response = requests.get(url, verify=False, timeout=10) # <-- 確保有 verify=False
        response.raise_for_status()
        data = response.json()
        
        loc_data = data.get("records", {}).get("location")
        if not loc_data:
            return "❌ 天氣資料結構異常，請稍後再試。"

        weather_elements = {
            e["elementName"]: e["time"] for e in loc_data[0].get("weatherElement", [])
        }
        
        needed_elements = ['Wx', 'PoP', 'MinT', 'MaxT']
        if not all(element in weather_elements for element in needed_elements):
            return "❌ 天氣預報資料不完整，請稍後再試。"

        weather_info = ["📍 口湖鄉 36 小時天氣預報："]
        labels = ['今早', '今晚', '明早']
        
        num_periods = min(len(weather_elements['Wx']), len(labels))

        for i in range(num_periods):
            try:
                wx_data = weather_elements['Wx'][i]['parameter']
                pop_data = weather_elements['PoP'][i]['parameter']
                min_t_data = weather_elements['MinT'][i]['parameter']
                max_t_data = weather_elements['MaxT'][i]['parameter']
                
                w_desc = wx_data["parameterName"]
                icon = next((val for key, val in ICON_MAP.items() if key in w_desc), '❓')
                
                start_time_str = weather_elements['Wx'][i]['startTime']
                end_time_str = weather_elements['Wx'][i]['endTime']

                start_time = datetime.fromisoformat(start_time_str).strftime("%m/%d %H:%M")
                end_time = datetime.fromisoformat(end_time_str).strftime("%H:%M")
                
                weather_info.append(
                    f"\n▪️ {labels[i]} ({start_time}~{end_time})\n"
                    f"　天氣：{w_desc} {icon}\n"
                    f"　降雨機率：{pop_data['parameterName']}%\n"
                    f"　氣溫：{min_t_data['parameterName']}°C ~ {max_t_data['parameterName']}°C"
                )
            except (KeyError, ValueError, IndexError) as e:
                logging.error(f"Weather data processing error at period {i}: {e}")
                weather_info.append(f"\n▪️ {labels[i]} 資料處理錯誤。")

        return "".join(weather_info)
    except (requests.RequestException, ValueError, Exception) as e:
        logging.error(f"Error fetching weather data: {e}")
        return "❌ 取得天氣資料失敗，請稍後再試。"

def get_tide_kouhu():
    """獲取口湖鄉潮汐預報（今日）"""
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={CWA_API_KEY}"
        response = requests.get(url, verify=False, timeout=10) # <-- 確保有 verify=False
        response.raise_for_status()
        data = response.json()

        forecasts = data.get("records", {}).get("TideForecasts", [])
        location_data = next((loc for loc in forecasts if loc["Location"]["LocationId"] == KOUHU_TIDE_LOCATION_ID), None)

        if not location_data:
            return "❌ 找不到口湖鄉潮汐預報資料。"
        
        daily_data = location_data.get("Location", {}).get("TimePeriods", {}).get("Daily", [])
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_tide_data = next((d for d in daily_data if d["Date"] == today_str), None)

        if not today_tide_data or not today_tide_data.get("Time"):
            return f"🌊 口湖鄉今日 ({datetime.now().strftime('%m/%d')}) 無潮汐資料。"

        tide_info = [f"🌊 口湖鄉今日 ({datetime.now().strftime('%m/%d')}) 潮汐預報："]
        for tide in today_tide_data["Time"]:
            try:
                tide_type = "退潮" if tide["Tide"] == "乾潮" else tide["Tide"]
                tide_time = datetime.fromisoformat(tide["DateTime"].replace("Z", "+00:00")).strftime("%H:%M")
                height = tide.get("TideHeights", {}).get("AboveChartDatum")
                height_str = f"潮高：{height}公分" if height is not None else "潮高：-"
                tide_info.append(f"▪️ {tide_type}：{tide_time} ({height_str})")
            except (KeyError, ValueError, IndexError) as e:
                logging.error(f"Tide data processing error: {e}")
                tide_info.append("　部分潮汐資料不完整。")
        
        return "\n".join(tide_info)
    except (requests.RequestException, ValueError, Exception) as e:
        logging.error(f"Error fetching tide data: {e}")
        return "❌ 取得潮汐資料失敗，請稍後再試。"

def get_typhoon():
    """獲取最新颱風資料"""
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={CWA_API_KEY}"
        response = requests.get(url, verify=False, timeout=10) # <-- 確保有 verify=False
        response.raise_for_status()
        data = response.json()
        
        typhoons = data.get("records", {}).get("tropicalCyclones", {}).get("tropicalCyclone", [])
        if not typhoons:
            return "📭 目前無活動颱風資訊。"
        
        latest_typhoon = typhoons[0]
        name = latest_typhoon.get("cwaTyphoonName", "未命名颱風")
        
        fix_data = latest_typhoon.get("analysisData", {}).get("fix")
        if not fix_data:
             return f"🌪️ 颱風：{name}，目前無詳細分析資料。"
        
        fix = fix_data[0]
        fix_time = datetime.fromisoformat(fix.get('fixTime', '')).strftime("%Y/%m/%d %H:%M")
        
        return (
            f"🌪️ 名稱：{name}\n"
            f"🕒 分析時間：{fix_time}\n"
            f"📍 座標：{fix.get('coordinate', '未知')}\n"
            f"💨 風速：{fix.get('maxWindSpeed', '未知')} m/s\n"
            f"🎯 方向：{fix.get('movingDirection', '未知')}\n"
            f"🧭 速度：{fix.get('movingSpeed', '未知')} km/h\n"
            f"🎈 中心氣壓：{fix.get('pressure', '未知')} hPa"
        )
    except (requests.RequestException, ValueError, Exception) as e:
        logging.error(f"Error fetching typhoon data: {e}")
        return "❌ 取得颱風資料失敗，請稍後再試。"


def get_earthquake():
    """獲取最新 3 筆有感地震資料"""
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={CWA_API_KEY}"
        response = requests.get(url, verify=False, timeout=10) # <-- 確保有 verify=False
        response.raise_for_status()
        data = response.json()
        
        earthquakes = data.get("records", {}).get("Earthquake", [])
        if not earthquakes:
            return "📡 目前無顯著有感地震資料。"

        recent_earthquakes = earthquakes[:3]
        
        earthquake_list = ["📡 最新有感地震："]
        for eq in recent_earthquakes:
            eq_info = eq.get("EarthquakeInfo")
            if not eq_info:
                continue

            origin_time = datetime.fromisoformat(eq_info.get('OriginTime', '')).strftime("%Y/%m/%d %H:%M")
            epicenter_loc = eq_info.get('Epicenter', {}).get('Location', '未知地點')
            magnitude = eq_info.get('EarthquakeMagnitude', {}).get('MagnitudeValue', '未知')
            focal_depth = eq_info.get('FocalDepth', '未知')

            earthquake_list.append(
                f"\n📍 地點：{epicenter_loc}\n"
                f"🕒 時間：{origin_time}\n"
                f"📏 規模：{magnitude}，深度：{focal_depth} 公里"
            )
        
        return "\n".join(earthquake_list)

    except (requests.RequestException, ValueError, Exception) as e:
        logging.error(f"Error fetching earthquake data: {e}")
        return "❌ 取得地震資料失敗，請稍後再試。"

def get_links_message():
    """產生常用連結的文字訊息"""
    return "📎 常用連結：\n" + "\n".join([f"🔹 {name}：{url}" for name, url in LINKS])

# --- 啟動程式 ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
