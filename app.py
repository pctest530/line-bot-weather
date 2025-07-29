from flask import Flask, request, abort, render_template_string
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests

app = Flask(__name__)

# ✅ 你的 LINE 設定
LINE_CHANNEL_ACCESS_TOKEN = "voGLDMSHC/Xfng1zq62Tn4pGDC2ZWwb7l+HrUj54NNqXy1SfAy3Bs/EKp64WLlwQaSQeomnS1JmIWCqugoovc9IxNQfp8vA1PNdxUpYanXVh/vEGAKb4yrufufYMhp+kGsT4fUx+I+HwNIzHTqqtbgdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "6362b12e044b913859b3772bf42cfa0d"
TO_USER_ID = "Uaaec86d0060844844df5bb2e731a375f"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ✅ 氣象局金鑰
CWA_API_KEY = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"

# ✅ 首頁顯示＋推播
@app.route("/")
def home():
    try:
        line_bot_api.push_message(
            TO_USER_ID,
            TextSendMessage(text="✅ LINE BOT 已啟動，歡迎使用。請輸入：天氣、潮汐、颱風 或 地震")
        )
    except Exception as e:
        return f"❌ 推播失敗：{str(e)}"

    links = [
        ("韌性防災", "https://yliflood.yunlin.gov.tw/cameralist/"),
        ("雲林路燈", "https://lamp.yunlin.gov.tw/slyunlin/Default.aspx"),
        ("管線挖掘", "https://pwd.yunlin.gov.tw/YLPub/"),
        ("台灣電力", "https://service.taipower.com.tw/nds/ndsWeb/ndft112.aspx"),
        ("停電查詢", "https://service.taipower.com.tw/branch/d120/xcnotice?xsmsid=0M242581310910082112"),
        ("自來水公司", "https://wateroff.water.gov.tw/"),
        ("清潔隊資訊", "https://epb.yunlin.gov.tw/files/11-1000-165.php")
    ]

    html = """
    <h2>✅ LINE BOT 已啟動，訊息已推送</h2>
    <p>您可以在 LINE 中輸入：「天氣」、「潮汐」、「颱風」、「地震」來查詢資訊。</p>
    <hr>
    <h3>🔗 常用連結</h3>
    <ul>
        {% for name, url in links %}
        <li><a href="{{ url }}" target="_blank">{{ name }}</a></li>
        {% endfor %}
    </ul>
    """
    return render_template_string(html, links=links)

# ✅ Webhook 接收 LINE 訊息
@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ✅ 處理使用者訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip().lower()
    user_id = event.source.user_id

    if msg == "id":
        res = f"你的 LINE 使用者 ID 是：\n{user_id}"
    elif "天氣" in msg:
        res = get_weather()
    elif "潮汐" in msg:
        res = get_tide()
    elif "颱風" in msg:
        res = get_typhoon()
    elif "地震" in msg:
        res = get_earthquake()
    else:
        res = "請輸入：天氣、潮汐、颱風 或 地震"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

# ---------- 天氣 ----------
def get_weather():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}&locationName=口湖鄉"
        r = requests.get(url).json()
        w = r["records"]["location"][0]["weatherElement"]
        res = []
        for i in range(3):
            t_start = w[0]["time"][i]["startTime"][5:16]
            t_end = w[0]["time"][i]["endTime"][11:16]
            weather = w[0]["time"][i]["parameter"]["parameterName"]
            pop = w[1]["time"][i]["parameter"]["parameterName"]
            minT = w[2]["time"][i]["parameter"]["parameterName"]
            maxT = w[4]["time"][i]["parameter"]["parameterName"]
            res.append(f"📅 {t_start}~{t_end}\n☁️ 天氣：{weather}\n🌧️ 降雨：{pop}%\n🌡️ 氣溫：{minT}~{maxT}°C")
        return "\n\n".join(res)
    except Exception as e:
        return f"❌ 天氣錯誤：{e}"

# ---------- 潮汐 ----------
def get_tide():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={CWA_API_KEY}"
        r = requests.get(url).json()
        for loc in r["records"]["TideForecasts"]:
            if loc["Location"]["LocationName"] == "口湖鄉":
                today = loc["Location"]["TimePeriods"]["Daily"][0]
                msg = [f"📅 日期：{today['Date']}"]
                for t in today["Time"]:
                    tide_type = "退潮" if t["Tide"] == "乾潮" else t["Tide"]
                    msg.append(f"{tide_type}：{t['DateTime'][11:16]}，{t['TideHeights']['AboveChartDatum']}cm")
                return "\n".join(msg)
        return "❌ 找不到口湖鄉潮汐資料"
    except Exception as e:
        return f"❌ 潮汐錯誤：{e}"

# ---------- 颱風 ----------
def get_typhoon():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={CWA_API_KEY}"
        r = requests.get(url).json()
        typhoons = r["records"]["tropicalCyclones"].get("tropicalCyclone", [])
        if not typhoons:
            return "📭 目前無颱風"
        latest = typhoons[0]
        name = latest.get("cwaTyphoonName", "未命名")
        fix = latest["analysisData"]["fix"][0]
        return (
            f"🌪️ 名稱：{name}\n📍 座標：{fix['coordinate']}\n"
            f"💨 風速：{fix['maxWindSpeed']} m/s\n🎯 方向：{fix['movingDirection']}\n"
            f"🧭 速度：{fix['movingSpeed']} km/h\n🎈 中心氣壓：{fix['pressure']} hPa"
        )
    except Exception as e:
        return f"❌ 颱風錯誤：{e}"

# ---------- 地震 ----------
def get_earthquake():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={CWA_API_KEY}"
        r = requests.get(url).json()
        eq = r["records"]["Earthquake"][0]["EarthquakeInfo"]
        return (
            f"📡 地震速報：\n📍 地點：{eq['Epicenter']['Location']}\n"
            f"🕒 時間：{eq['OriginTime']}\n📏 規模：{eq['EarthquakeMagnitude']['MagnitudeValue']}，深度：{eq['FocalDepth']} km"
        )
    except Exception as e:
        return f"❌ 地震錯誤：{e}"

if __name__ == "__main__":
    app.run()
