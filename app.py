from flask import Flask, request, abort, render_template_string
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
from datetime import datetime

app = Flask(__name__)

# ✅ 你的 LINE 憑證資訊
LINE_CHANNEL_ACCESS_TOKEN = "voGLDMSHC/Xfng1zq62Tn4pGDC2ZWwb7l+HrUj54NNXy1SfAy3Bs/EKp64WLlwQaSQeomnS1JmIWCqugoovc9IxNQfp8vA1PNdxUpYanXVh/vEGAKb4yrufufYMhp+kGsT4fUx+I+HwNIzHTqqtbgdB04t89/1O/w1cDnyilFU=" # 請替換為您的實際 Token
LINE_CHANNEL_SECRET = "6362b12e044b913859b3772bf42cfa0d" # 請替換為您的實際 Secret
TO_USER_ID = "Uaaec86d0060844844df5bb2e731a375f" # 請替換為您的實際 User ID

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ✅ 氣象局金鑰
CWA_API_KEY = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"

# 天氣圖示對應
ICON_MAP = {
    '晴': '☀️', '多雲': '⛅', '陰': '☁️',
    '小雨': '🌧️', '陣雨': '🌦️', '雷陣雨': '⛈️',
    '雨': '🌧️', '短暫陣雨': '🌦️', '局部雨': '🌦️',
    '雷': '⚡'
}

# ✅ 首頁自動推播＋連結顯示
@app.route("/")
def home():
    try:
        line_bot_api.push_message(
            TO_USER_ID,
            TextSendMessage(text="✅ LINE BOT 已啟動，請輸入：天氣、潮汐、颱風、地震、連結")
        )
    except Exception as e:
        return f"❌ 推播失敗：{str(e)}"

    links = get_links()
    html = """
    <h2>✅ LINE BOT 已啟動</h2>
    <p>輸入：「天氣」、「潮汐」、「颱風」、「地震」、「連結」查看資訊</p>
    <hr>
    <h3>🔗 常用連結</h3>
    <ul>
        {% for name, url in links %}
        <li><a href="{{ url }}" target="_blank">{{ name }}</a></li>
        {% endfor %}
    </ul>
    """
    return render_template_string(html, links=links)

# ✅ webhook 註冊點
@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ✅ 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    user_id = event.source.user_id

    if msg == "id":
        res = f"你的 LINE 使用者 ID 是：\n{user_id}"
    elif msg in ["天氣", "口湖天氣"]:
        res = get_weather_kouhu()
    elif msg == "潮汐":
        res = get_tide_kouhu()
    elif msg == "颱風":
        res = get_typhoon()
    elif msg == "地震":
        res = get_earthquake()
    elif msg == "連結":
        links = get_links()
        res = "📎 常用連結：\n" + "\n".join([f"🔹 {name}：{url}" for name, url in links])
    else:
        res = "請輸入：天氣、潮汐、颱風、地震 或 連結"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

# --- 新增的天氣功能 ---
def get_weather_kouhu():
    """獲取口湖鄉 36 小時天氣預報"""
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}&locationName=雲林縣"
        # 修正：加入 verify=False
        r = requests.get(url, verify=False).json()
        
        loc = r["records"]["location"][0]
        wx_elements = loc["weatherElement"]

        # 找到需要的氣象元素
        wx = next((e for e in wx_elements if e["elementName"] == 'Wx'), None)
        pop = next((e for e in wx_elements if e["elementName"] == 'PoP'), None)
        min_t = next((e for e in wx_elements if e["elementName"] == 'MinT'), None)
        max_t = next((e for e in wx_elements if e["elementName"] == 'MaxT'), None)

        if not all([wx, pop, min_t, max_t]):
            return "❌ 天氣資料不完整，請稍後再試。"

        labels = ['今早', '今晚', '明早']
        weather_info = "📍 口湖鄉 36 小時天氣預報：\n\n"

        for i in range(min(len(wx["time"]), len(pop["time"]), len(min_t["time"]), len(max_t["time"]))):
            w_desc = wx["time"][i]["parameter"]["parameterName"]
            pop_value = pop["time"][i]["parameter"]["parameterName"]
            min_temp = min_t["time"][i]["parameter"]["parameterName"]
            max_temp = max_t["time"][i]["parameter"]["parameterName"]

            # 找出最符合的圖示
            icon = '❓'
            for key, val in ICON_MAP.items():
                if key in w_desc:
                    icon = val
                    break
            
            start_time_obj = datetime.fromisoformat(wx["time"][i]["startTime"])
            end_time_obj = datetime.fromisoformat(wx["time"][i]["endTime"])
            
            # 格式化時間，只顯示月/日 時:分
            start_time_formatted = start_time_obj.strftime("%m/%d %H:%M")
            end_time_formatted = end_time_obj.strftime("%m/%d %H:%M")

            weather_info += (
                f"▪️ {labels[i]} ({start_time_formatted} ~ {end_time_formatted})\n"
                f"　天氣：{w_desc} {icon}\n"
                f"　降雨機率：{pop_value}%\n"
                f"　氣溫：{min_temp}°C ~ {max_temp}°C\n"
            )
            if i < 2: # 避免最後一個時段後面也多一個換行
                weather_info += "\n"

        return weather_info
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return f"❌ 取得天氣資料失敗，請稍後再試。"

# --- 新增的潮汐功能 ---
def get_tide_kouhu():
    """獲取口湖鄉潮汐預報（今日）"""
    LOCATION_ID = "10009190" # 口湖鄉
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={CWA_API_KEY}"
        # 修正：加入 verify=False
        r = requests.get(url, verify=False).json()

        if r.get("success") not in ["true", True]:
            return "❌ 潮汐資料 API 回傳失敗。"

        forecasts = r["records"]["TideForecasts"]
        location_data = next((loc for loc in forecasts if loc["Location"]["LocationId"] == LOCATION_ID), None)

        if not location_data:
            return "找不到口湖鄉潮汐預報資料。"
        
        all_daily_data = location_data["Location"]["TimePeriods"]["Daily"]
        
        # 取得今天日期字串 (YYYY-MM-DD)
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_data = next((d for d in all_daily_data if d["Date"] == today_str), None)

        if not today_data:
            return "今日口湖鄉無潮汐資料。"

        tide_info = "🌊 口湖鄉今日潮汐預報：\n"
        for tide in today_data["Time"]:
            tide_type = "退潮" if tide["Tide"] == "乾潮" else tide["Tide"]
            tide_time = datetime.fromisoformat(tide["DateTime"]).strftime("%H:%M") # 只顯示時間
            height = tide["TideHeights"].get("AboveChartDatum", "-")

            tide_info += f"▪️ {tide_type}：{tide_time} (潮高：{height}公分)\n"
        
        return tide_info.strip() # 移除末尾多餘的換行
    except Exception as e:
        print(f"Error fetching tide: {e}")
        return f"❌ 取得潮汐資料失敗，請稍後再試。"

# ✅ 颱風資料（API）
def get_typhoon():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={CWA_API_KEY}"
        r = requests.get(url, verify=False).json()
        typhoons = r["records"]["tropicalCyclones"].get("tropicalCyclone", [])
        if not typhoons:
            return "📭 目前無颱風"
        latest = typhoons[0]
        name = latest.get("cwaTyphoonName", "未命名")
        
        # 檢查 analysisData 和 fix 是否存在
        analysis_data = latest.get("analysisData")
        if not analysis_data or not analysis_data.get("fix"):
            return f"🌪️ 颱風：{name}，目前無詳細分析資料。"
            
        fix = analysis_data["fix"][0]
        
        # 格式化 fixTime
        fix_time_obj = datetime.fromisoformat(fix['fixTime'])
        fix_time_formatted = fix_time_obj.strftime("%Y/%m/%d %H:%M")

        return (
            f"🌪️ 名稱：{name}\n"
            f"🕒 分析時間：{fix_time_formatted}\n"
            f"📍 座標：{fix['coordinate']}\n"
            f"💨 風速：{fix['maxWindSpeed']} m/s\n"
            f"🎯 方向：{fix['movingDirection']}\n"
            f"🧭 速度：{fix['movingSpeed']} km/h\n"
            f"🎈 中心氣壓：{fix['pressure']} hPa"
        )
    except Exception as e:
        print(f"Error fetching typhoon: {e}")
        return f"❌ 颱風資料錯誤：{e}"

# ✅ 地震資料（API）
def get_earthquake():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={CWA_API_KEY}"
        r = requests.get(url, verify=False).json()
        
        earthquakes = r["records"].get("Earthquake", [])
        if not earthquakes:
            return "📡 目前無顯著有感地震資料。"
        
        eq = earthquakes[0].get("EarthquakeInfo")
        if not eq:
            return "📡 無法取得地震詳細資訊。"

        # 格式化 OriginTime
        origin_time_obj = datetime.fromisoformat(eq['OriginTime'])
        origin_time_formatted = origin_time_obj.strftime("%Y/%m/%d %H:%M")

        return (
            f"📡 地震速報：\n"
            f"📍 地點：{eq['Epicenter']['Location']}\n"
            f"🕒 時間：{origin_time_formatted}\n"
            f"📏 規模：{eq['EarthquakeMagnitude']['MagnitudeValue']}，深度：{eq['FocalDepth']} 公里"
        )
    except Exception as e:
        print(f"Error fetching earthquake: {e}")
        return f"❌ 地震資料錯誤：{e}"

# ✅ 常用連結清單
def get_links():
    return [
        ("韌性防災", "https://yliflood.yunlin.gov.tw/cameralist/"),
        ("雲林路燈", "https://lamp.yunlin.gov.tw/slyunlin/Default.aspx"),
        ("管線挖掘", "https://pwd.yunlin.gov.tw/YLPub/"),
        ("台灣電力", "https://service.taipower.com.tw/nds/ndsWeb/ndft112.aspx"),
        ("停電查詢", "https://service.taipower.com.tw/branch/d120/xcnotice?xsmsid=0M242581310910082112"),
        ("自來水公司", "https://wateroff.water.gov.tw/"),
        ("清潔隊資訊", "https://epb.yunlin.gov.tw/files/11-1000-165.php")
    ]

if __name__ == "__main__":
    # 在實際部署時，請確保 host="0.0.0.0" 並使用 WSGI 伺服器 (如 Gunicorn)
    # 並設定 debug=False
    app.run(debug=True, port=5000)
