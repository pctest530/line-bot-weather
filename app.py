from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests

app = Flask(__name__)

# ✅ 你的 LINE Token 和 Secret（請部署完後更新密鑰以防安全問題）
LINE_CHANNEL_ACCESS_TOKEN = "voGLDMSHC/Xfng1zq62Tn4pGDC2ZWwb7l+HrUj54NNqXy1SfAy3Bs/EKp64WLlwQaSQeomnS1JmIWCqugoovc9IxNQfp8vA1PNdxUpYanXVh/vEGAKb4yrufufYMhp+kGsT4fUx+I+HwNIzHTqqtbgdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "6362b12e044b913859b3772bf42cfa0d"

# ✅ 替換成你自己的 User ID，暫時寫空白方便測試
TO_USER_ID = "填入你的 LINE User ID"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/")
def home():
    try:
        line_bot_api.push_message(TO_USER_ID, TextSendMessage(text="✅ 測試成功：首頁已自動發送訊息"))
        return "LINE Bot Webhook 已上線，已發送測試訊息"
    except Exception as e:
        return f"❌ 發送失敗：{str(e)}"

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
    
    if msg == "天氣" or msg == "口湖天氣":
        res = get_weather()
    elif msg == "潮汐":
        res = get_tide()
    elif msg == "颱風":
        res = get_typhoon()
    elif msg == "地震":
        res = get_earthquake()
    else:
        res = "請輸入關鍵字：天氣、潮汐、颱風 或 地震"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

# ---------- CWA 氣象 API Key ----------
CWA_API_KEY = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"

# ---------- 天氣 ----------
def get_weather():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}&locationName=口湖鄉"
        r = requests.get(url).json()
        w = r["records"]["location"][0]["weatherElement"]
        res = []
        for i in range(3):
            start = w[0]["time"][i]["startTime"][5:16]
            end = w[0]["time"][i]["endTime"][11:16]
            weather = w[0]["time"][i]["parameter"]["parameterName"]
            pop = w[1]["time"][i]["parameter"]["parameterName"]
            minT = w[2]["time"][i]["parameter"]["parameterName"]
            maxT = w[4]["time"][i]["parameter"]["parameterName"]
            res.append(f"📅 {start}~{end}\n☁️ 天氣：{weather}\n🌧️ 降雨：{pop}%\n🌡️ 氣溫：{minT}~{maxT}°C")
        return "\n\n".join(res)
    except Exception as e:
        return f"❌ 天氣資料錯誤：{str(e)}"

# ---------- 潮汐 ----------
def get_tide():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={CWA_API_KEY}"
        r = requests.get(url).json()
        forecasts = r["records"]["TideForecasts"]
        for loc in forecasts:
            if loc["Location"]["LocationName"] == "口湖鄉":
                today = loc["Location"]["TimePeriods"]["Daily"][0]
                msg = [f"📅 日期：{today['Date']}"]
                for t in today["Time"]:
                    type_ = "退潮" if t["Tide"] == "乾潮" else t["Tide"]
                    msg.append(f"{type_}：{t['DateTime'][11:16]}，{t['TideHeights']['AboveChartDatum']}cm")
                return "\n".join(msg)
        return "❌ 找不到口湖鄉潮汐資料"
    except Exception as e:
        return f"❌ 潮汐資料錯誤：{str(e)}"

# ---------- 颱風 ----------
def get_typhoon():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={CWA_API_KEY}"
        r = requests.get(url).json()
        cyclones = r["records"]["tropicalCyclones"]["tropicalCyclone"]
        if not cyclones:
            return "📭 目前無活動颱風"
        latest = cyclones[0]
        name = latest.get("cwaTyphoonName", "未命名")
        fix = latest["analysisData"]["fix"][0]
        info = f"🌪️ 名稱：{name}\n📍 座標：{fix['coordinate']}\n💨 風速：{fix['maxWindSpeed']} m/s\n🎯 方向：{fix['movingDirection']}\n🧭 速度：{fix['movingSpeed']} km/h\n🎈 中心氣壓：{fix['pressure']} hPa"
        return info
    except Exception as e:
        return f"❌ 颱風資料錯誤：{str(e)}"

# ---------- 地震 ----------
def get_earthquake():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={CWA_API_KEY}"
        r = requests.get(url).json()
        quake = r["records"]["Earthquake"][0]["EarthquakeInfo"]
        time = quake["OriginTime"]
        loc = quake["Epicenter"]["Location"]
        mag = quake["EarthquakeMagnitude"]["MagnitudeValue"]
        depth = quake["FocalDepth"]
        return f"📡 最新地震速報：\n📍 震央：{loc}\n🕒 時間：{time}\n📏 規模：{mag}，深度：{depth} 公里"
    except Exception as e:
        return f"❌ 地震資料錯誤：{str(e)}"

if __name__ == "__main__":
    app.run()
