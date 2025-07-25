from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import requests

app = Flask(__name__)

# 環境變數
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 氣象局 API 金鑰
CWA_API_KEY = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"

# ----- Webhook -----
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ----- 文字處理 -----
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()

    if msg == "口湖天氣":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=get_weather()))
    elif msg == "潮汐":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=get_tide()))
    elif msg == "地震":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=get_quake()))
    elif msg == "颱風":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=get_typhoon()))
    elif msg == "連結":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=get_links()))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入：口湖天氣、潮汐、地震、颱風 或 連結"))

# ===== 功能實作 =====

def get_weather():
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}&locationName=雲林縣"
    try:
        res = requests.get(url).json()
        loc = res["records"]["location"][0]
        wx = loc["weatherElement"][0]["time"]
        minT = loc["weatherElement"][2]["time"]
        maxT = loc["weatherElement"][4]["time"]

        result = "🌤️ 口湖 36 小時天氣：\n"
        for i in range(3):
            period = wx[i]["startTime"][5:16].replace("-", "/")
            weather = wx[i]["parameter"]["parameterName"]
            low = minT[i]["parameter"]["parameterName"]
            high = maxT[i]["parameter"]["parameterName"]
            result += f"\n🕒 {period}\n☁️ 天氣：{weather}\n🌡️ 溫度：{low}°C ~ {high}°C\n"

        return result
    except Exception as e:
        return f"❌ 天氣資料讀取失敗：{e}"

def get_tide():
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={CWA_API_KEY}"
    try:
        res = requests.get(url).json()
        forecasts = res["records"]["TideForecasts"]
        target = next((f for f in forecasts if f["Location"]["LocationId"] == "10009190"), None)
        if not target:
            return "❌ 找不到口湖鄉潮汐資料"
        today = target["Location"]["TimePeriods"]["Daily"][0]
        lines = ["🌊 今日潮汐："]
        for t in today["Time"]:
            type_name = "退潮" if t["Tide"] == "乾潮" else t["Tide"]
            height = t["TideHeights"]["AboveChartDatum"]
            time = t["DateTime"][-8:-3]
            lines.append(f"{type_name}：{time}，{height} cm")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 潮汐資料錯誤：{e}"

def get_quake():
    try:
        main_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={CWA_API_KEY}&limit=1"
        local_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0016-001?Authorization={CWA_API_KEY}&limit=1"
        res1 = requests.get(main_url).json()
        res2 = requests.get(local_url).json()

        info = "📡 地震速報\n"

        for r in [res1, res2]:
            quake = r["records"].get("Earthquake", [])
            if not quake:
                continue
            q = quake[0]["EarthquakeInfo"]
            loc = q.get("Epicenter", {}).get("Location", "未知")
            time = q.get("OriginTime", "")[5:16]
            mag = q.get("EarthquakeMagnitude", {}).get("MagnitudeValue", "?")
            depth = q.get("FocalDepth", "?")
            info += f"\n📍 地點：{loc}\n🕒 時間：{time}\n📏 規模：{mag}，深度：{depth} 公里\n"

        return info or "✅ 無地震速報"
    except Exception as e:
        return f"❌ 地震資料錯誤：{e}"

def get_typhoon():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={CWA_API_KEY}"
        res = requests.get(url).json()
        cyclones = res["records"].get("tropicalCyclones", {}).get("tropicalCyclone", [])
        if not cyclones:
            return "✅ 目前無活動颱風"

        t = cyclones[0]
        name = t.get("cwaTyphoonName", "未命名")
        fix = t["analysisData"]["fix"][0]
        txt = f"🌀 颱風：{name}\n🕒 時間：{fix['fixTime']}\n📍 座標：{fix['coordinate']}\n💨 最大風速：{fix['maxWindSpeed']} m/s\n"
        txt += f"🎯 方向：{fix['movingDirection']}，{fix['movingSpeed']} km/h\n🎈 氣壓：{fix['pressure']} hPa"

        return txt
    except Exception as e:
        return f"❌ 颱風資料錯誤：{e}"

def get_links():
    return (
        "🔗 常用連結：\n"
        "📷 [韌性防災](https://yliflood.yunlin.gov.tw/cameralist/#)\n"
        "💡 [雲林路燈](https://lamp.yunlin.gov.tw/slyunlin/Default.aspx)\n"
        "🚧 [管線挖掘](https://pwd.yunlin.gov.tw/YLPub/)\n"
        "⚡ [台灣電力](https://service.taipower.com.tw/nds/ndsWeb/ndft112.aspx)\n"
        "🔌 [停電查詢](https://service.taipower.com.tw/branch/d120/xcnotice?xsmsid=0M242581310910082112)\n"
        "🚰 [自來水](https://web.water.gov.tw/wateroff/)\n"
        "🌐 [氣象署官網](https://www.cwa.gov.tw/V8/C/)"
    )

# ----- 主程式入口 -----
if __name__ == "__main__":
    app.run()
