from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os

app = Flask(__name__)

# --- 直接填入你的 Token & Secret ---
LINE_CHANNEL_ACCESS_TOKEN = "voGLDMSHC/Xfng1zq62Tn4pGDC2ZWwb7l+HrUj54NNqXy1SfAy3Bs/EKp64WLlwQaSQeomnS1JmIWCqugoovc9IxNQfp8vA1PNdxUpYanXVh/vEGAKb4yrufufYMhp+kGsT4fUx+I+HwNIzHTqqtbgdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "6362b12e044b913859b3772bf42cfa0d"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/")
def home():
    return "LINE Bot 已部署成功"

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ---------- 回應文字訊息 ----------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    try:
        if msg in ["天氣", "口湖天氣"]:
            res = get_weather()
        elif msg == "潮汐":
            res = get_tide()
        elif msg == "颱風":
            res = get_typhoon()
        elif msg == "地震":
            res = get_earthquake()
        elif msg == "連結":
            res = get_links()
        else:
            res = "請輸入：天氣、潮汐、颱風、地震 或 連結"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))
    except Exception as e:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❌ 系統錯誤：{str(e)}"))

# ---------- 從 GitHub 頁面抓網頁資料 ----------
def get_weather():
    try:
        html = requests.get("https://pctest530.github.io/weather/").text
        start = html.find("口湖鄉 36 小時天氣")
        weather_data = html[start:start + 500]
        return "📍口湖鄉天氣（擷取）：\n" + weather_data
    except Exception as e:
        return f"❌ 天氣載入錯誤：{str(e)}"

def get_tide():
    try:
        html = requests.get("https://pctest530.github.io/weather/").text
        start = html.find("口湖鄉潮汐預報")
        tide_data = html[start:start + 500]
        return "🌊 潮汐預報（擷取）：\n" + tide_data
    except Exception as e:
        return f"❌ 潮汐載入錯誤：{str(e)}"

# ---------- API 方式維持不變 ----------
def get_typhoon():
    try:
        url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization=CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"
        r = requests.get(url).json()
        cyclones = r["records"]["tropicalCyclones"]["tropicalCyclone"]
        if not cyclones:
            return "📭 目前無活動颱風"
        latest = cyclones[0]
        name = latest.get("cwaTyphoonName", "未命名")
        fix = latest["analysisData"]["fix"][0]
        info = f"🌪️ 名稱：{name}\n📍 座標：{fix['coordinate']}\n💨 風速：{fix['maxWindSpeed']} m/s\n🎯 方向：{fix['movingDirection']}\n🧭 速度：{fix['movingSpeed']} km/h\n🎈 氣壓：{fix['pressure']} hPa"
        return info
    except Exception as e:
        return f"❌ 颱風資料錯誤：{str(e)}"

def get_earthquake():
    try:
        url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization=CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"
        r = requests.get(url).json()
        quake = r["records"]["Earthquake"][0]["EarthquakeInfo"]
        return f"📡 最新地震：\n震央：{quake['Epicenter']['Location']}\n時間：{quake['OriginTime']}\n規模：{quake['EarthquakeMagnitude']['MagnitudeValue']}，深度：{quake['FocalDepth']} 公里"
    except Exception as e:
        return f"❌ 地震資料錯誤：{str(e)}"

# ---------- 常用連結 ----------
def get_links():
    return """🔗 常用連結：
1️⃣ 韌性防災：https://yliflood.yunlin.gov.tw/cameralist/#
2️⃣ 雲林路燈：https://lamp.yunlin.gov.tw/slyunlin/Default.aspx
3️⃣ 管線挖掘：https://pwd.yunlin.gov.tw/YLPub/
4️⃣ 台灣電力：https://service.taipower.com.tw/nds/ndsWeb/ndft112.aspx
5️⃣ 停電查詢：https://service.taipower.com.tw/branch/d120/xcnotice?xsmsid=0M242581310910082112
6️⃣ 自來水：https://web.water.gov.tw/wateroff/
7️⃣ 氣象署官網：https://www.cwa.gov.tw/V8/C/
"""

if __name__ == "__main__":
    app.run()
