from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import requests
from datetime import datetime

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = "voGLDMSHC/..."  # ← 你的 token
LINE_CHANNEL_SECRET = "6362b12e044b913859b3772bf42cfa0d"
CWA_API_KEY = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/")
def home():
    return "LINE Bot Webhook 已上線"

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
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
        res = "請輸入關鍵字：天氣、潮汐、颱風、地震 或 連結"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

def get_weather():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}&locationName=雲林縣"
        r = requests.get(url, timeout=10).json()
        loc = r["records"]["location"][0]
        t = next(e["time"] for e in loc["weatherElement"] if e["elementName"] == "Wx")
        pop = next(e["time"] for e in loc["weatherElement"] if e["elementName"] == "PoP")
        minT = next(e["time"] for e in loc["weatherElement"] if e["elementName"] == "MinT")
        maxT = next(e["time"] for e in loc["weatherElement"] if e["elementName"] == "MaxT")

        labels = ["今早", "今晚", "明早"]
        lines = []
        for i in range(3):
            w = t[i]["parameter"]["parameterName"]
            p = pop[i]["parameter"]["parameterName"]
            lT = minT[i]["parameter"]["parameterName"]
            hT = maxT[i]["parameter"]["parameterName"]
            st = t[i]["startTime"][5:16].replace(" ", "~")
            et = t[i]["endTime"][11:16]
            lines.append(f"{labels[i]}（{st}~{et}）\n☁️ 天氣：{w}\n🌧️ 降雨機率：{p}%\n🌡️ 氣溫：{lT}~{hT}°C")
        return "\n\n".join(lines)
    except Exception as e:
        return f"❌ 天氣資料錯誤：{e}"

def get_tide():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={CWA_API_KEY}"
        r = requests.get(url, timeout=10).json()
        forecasts = r["records"]["TideForecasts"]
        loc = next((f for f in forecasts if f["Location"]["LocationId"] == "10009190"), None)
        if not loc:
            return "❌ 找不到口湖鄉潮汐預報"
        today = datetime.now().strftime("%Y-%m-%d")
        daily = next((d for d in loc["Location"]["TimePeriods"]["Daily"] if d["Date"] == today), None)
        if not daily:
            return "今日無潮汐資料"
        msg = [f"📅 日期：{daily['Date']}"]
        for t in daily["Time"]:
            kind = "退潮" if t["Tide"] == "乾潮" else t["Tide"]
            time = datetime.strptime(t["DateTime"], "%Y-%m-%dT%H:%M:%S+08:00").strftime("%H:%M")
            height = t["TideHeights"]["AboveChartDatum"]
            msg.append(f"{kind}：{time}，{height} cm")
        return "\n".join(msg)
    except Exception as e:
        return f"❌ 潮汐資料錯誤：{e}"

def get_typhoon():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={CWA_API_KEY}"
        r = requests.get(url, timeout=10).json()
        cyclones = r["records"]["tropicalCyclones"]["tropicalCyclone"]
        if not cyclones:
            return "📭 目前無活動颱風"
        c = cyclones[0]
        fix = c["analysisData"]["fix"][0]
        return f"🌪️ 名稱：{c.get('cwaTyphoonName', '未命名')}\n📍 座標：{fix['coordinate']}\n💨 風速：{fix['maxWindSpeed']} m/s\n🎯 方向：{fix['movingDirection']}\n🧭 速度：{fix['movingSpeed']} km/h\n🎈 中心氣壓：{fix['pressure']} hPa"
    except Exception as e:
        return f"❌ 颱風資料錯誤：{e}"

def get_earthquake():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={CWA_API_KEY}"
        r = requests.get(url, timeout=10).json()
        q = r["records"]["Earthquake"][0]["EarthquakeInfo"]
        t = q["OriginTime"]
        loc = q["Epicenter"]["Location"]
        mag = q["EarthquakeMagnitude"]["MagnitudeValue"]
        dep = q["FocalDepth"]
        return f"📡 地震速報：\n📍 震央：{loc}\n🕒 時間：{t}\n📏 規模：{mag}，深度：{dep} 公里"
    except Exception as e:
        return f"❌ 地震資料錯誤：{e}"

def get_links():
    return (
        "🔗 常用連結：\n"
        "1️⃣ 韌性防災\nhttps://yliflood.yunlin.gov.tw/cameralist/#\n"
        "2️⃣ 雲林路燈\nhttps://lamp.yunlin.gov.tw/slyunlin/Default.aspx\n"
        "3️⃣ 管線挖掘\nhttps://pwd.yunlin.gov.tw/YLPub/\n"
        "4️⃣ 台灣電力\nhttps://service.taipower.com.tw/nds/ndsWeb/ndft112.aspx\n"
        "5️⃣ 停電查詢\nhttps://service.taipower.com.tw/branch/d120/xcnotice?xsmsid=0M242581310910082112\n"
        "6️⃣ 自來水\nhttps://web.water.gov.tw/wateroff/\n"
        "7️⃣ 氣象署\nhttps://www.cwa.gov.tw/V8/C/"
    )

if __name__ == "__main__":
    app.run()
