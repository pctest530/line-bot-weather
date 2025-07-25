from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import requests

app = Flask(__name__)

# 從 Render 的環境變數取得 token 與 secret
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 氣象局 API 金鑰
cwa_api_key = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"

@app.route("/")
def index():
    return "LINE BOT 已上線！"

@app.route("/callback", methods=['POST'])
def callback():
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
        reply = get_weather()
    elif msg == "潮汐":
        reply = get_tide()
    elif msg == "地震":
        reply = get_earthquake()
    elif msg == "颱風":
        reply = get_typhoon()
    elif msg == "連結":
        reply = (
            "🔗 常用連結：\n"
            "1. 韌性防災：https://yliflood.yunlin.gov.tw/cameralist/#\n"
            "2. 雲林路燈：https://lamp.yunlin.gov.tw/slyunlin/Default.aspx\n"
            "3. 管線挖掘：https://pwd.yunlin.gov.tw/YLPub/\n"
            "4. 台灣電力：https://service.taipower.com.tw/nds/ndsWeb/ndft112.aspx\n"
            "5. 停電查詢：https://service.taipower.com.tw/branch/d120/xcnotice?xsmsid=0M242581310910082112\n"
            "6. 自來水：https://web.water.gov.tw/wateroff/\n"
            "7. 氣象局：https://www.cwa.gov.tw/V8/C/"
        )
    else:
        reply = "請輸入以下關鍵字：天氣、潮汐、地震、颱風、連結"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# --- 各功能 ---

def get_weather():
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={cwa_api_key}&locationName=口湖鄉"
    try:
        res = requests.get(url, timeout=5).json()
        loc = res['records']['location'][0]
        t = loc['weatherElement'][0]['time'][0]
        wx = t['parameter']['parameterName']
        st = t['startTime'][11:16]
        et = t['endTime'][11:16]
        return f"📍 口湖鄉天氣：{wx}\n時間：{st}~{et}"
    except:
        return "❌ 天氣資料讀取失敗"

def get_tide():
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={cwa_api_key}"
    try:
        res = requests.get(url, timeout=5).json()
        forecasts = res["records"]["TideForecasts"]
        loc = next((f for f in forecasts if f["Location"]["LocationId"] == "10009190"), None)
        if not loc:
            return "❌ 找不到口湖鄉潮汐資料"
        today = loc["Location"]["TimePeriods"]["Daily"][0]
        lines = [f"📅 {today['Date']} 潮汐資訊："]
        for t in today["Time"]:
            tt = t["Tide"]
            time = t["DateTime"][11:16]
            height = t["TideHeights"]["AboveChartDatum"]
            lines.append(f"{tt}：{time}，潮高：{height} 公分")
        return "\n".join(lines)
    except:
        return "❌ 潮汐資料讀取失敗"

def get_earthquake():
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={cwa_api_key}&limit=1"
    try:
        res = requests.get(url, timeout=5).json()
        eq = res["records"]["Earthquake"][0]["EarthquakeInfo"]
        time = eq["OriginTime"][11:16]
        loc = eq["Epicenter"]["Location"]
        mag = eq["EarthquakeMagnitude"]["MagnitudeValue"]
        return f"📡 最近地震：{time}\n震央：{loc}\n規模：{mag}"
    except:
        return "❌ 地震資料讀取失敗"

def get_typhoon():
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={cwa_api_key}"
    try:
        res = requests.get(url, timeout=5).json()
        typhoons = res["records"].get("tropicalCyclones", {}).get("tropicalCyclone", [])
        if not typhoons:
            return "📭 目前無颱風活動"
        name = typhoons[0].get("cwaTyphoonName", "未命名")
        time = typhoons[0].get("analysisData", {}).get("fix", [{}])[0].get("fixTime", "")
        return f"🌀 最新颱風：{name}\n更新時間：{time}"
    except:
        return "❌ 颱風資料讀取失敗"

# --- 主程式執行點 ---
if __name__ == "__main__":
    app.run()
