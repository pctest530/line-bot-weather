from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import requests
from datetime import datetime

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

APIKEY = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"  # 你的氣象局授權碼

def fetch_weather():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={APIKEY}&locationName=雲林縣"
        res = requests.get(url, timeout=7)
        data = res.json()
        loc = data["records"]["location"][0]
        wx = loc["weatherElement"]
        desc = []
        for elem in wx:
            if elem["elementName"] == "Wx":
                desc.append(elem["time"][0]["parameter"]["parameterName"])
            elif elem["elementName"] == "PoP":
                desc.append(f"降雨機率 {elem['time'][0]['parameter']['parameterName']}%")
            elif elem["elementName"] == "MinT":
                desc.append(f"最低溫度 {elem['time'][0]['parameter']['parameterName']}°C")
            elif elem["elementName"] == "MaxT":
                desc.append(f"最高溫度 {elem['time'][0]['parameter']['parameterName']}°C")
        return "36小時天氣：\n" + "\n".join(desc)
    except:
        return "天氣資料讀取失敗"

def fetch_typhoon():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={APIKEY}"
        res = requests.get(url, timeout=7)
        data = res.json()
        cyclones = data.get("records", {}).get("tropicalCyclones", {}).get("tropicalCyclone", [])
        if not cyclones:
            return "目前無活動颱風"
        c = cyclones[0]  # 取第一個颱風
        name = c.get("cwaTyphoonName") or c.get("typhoonName") or "未命名"
        fix = c.get("analysisData", {}).get("fix", [{}])[0]
        fixTime = fix.get("fixTime", "")
        pressure = fix.get("pressure", "")
        maxWindSpeed = fix.get("maxWindSpeed", "")
        movingDirection = fix.get("movingDirection", "")
        movingSpeed = fix.get("movingSpeed", "")
        gust = fix.get("maxGustSpeed", "")
        reply = (f"颱風名稱：{name}\n"
                 f"最新分析時間：{fixTime}\n"
                 f"氣壓：{pressure} hPa\n"
                 f"最大風速：{maxWindSpeed} m/s\n"
                 f"陣風：{gust} m/s\n"
                 f"移動方向：{movingDirection}\n"
                 f"移動速度：{movingSpeed} km/h")
        return reply
    except:
        return "颱風資料讀取失敗"

def format_time(tstr):
    try:
        d = datetime.fromisoformat(tstr)
        ampm = "上午" if d.hour < 12 else "下午"
        hour = d.hour % 12 or 12
        return f"{d.year}/{d.month}/{d.day} {ampm} {hour}:{d.minute:02d}"
    except:
        return tstr

def fetch_earthquake():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={APIKEY}&limit=3"
        res = requests.get(url, timeout=7)
        data = res.json()
        eqs = data.get("records", {}).get("Earthquake", [])
        if not eqs:
            return "目前無地震資料"
        messages = []
        for eq in eqs:
            info = eq.get("EarthquakeInfo", {})
            loc = info.get("Epicenter", {}).get("Location", "未知地點")
            mag = info.get("EarthquakeMagnitude", {}).get("MagnitudeValue", "未知")
            depth = info.get("FocalDepth", "未知")
            time = format_time(info.get("OriginTime", ""))
            messages.append(f"震央：{loc}\n時間：{time}\n規模：{mag}\n深度：{depth} 公里")
        return "顯著有感地震（最近3筆）：\n\n" + "\n\n".join(messages)
    except:
        return "地震資料讀取失敗"

def fetch_tide():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={APIKEY}"
        res = requests.get(url, timeout=7)
        data = res.json()
        forecasts = data.get("records", {}).get("TideForecasts", [])
        loc_data = None
        for loc in forecasts:
            if loc.get("Location", {}).get("LocationName") == "口湖":
                loc_data = loc
                break
        if not loc_data:
            return "找不到口湖鄉潮汐資料"
        today = datetime.now().strftime("%Y-%m-%d")
        tides = []
        for day in loc_data.get("Location", {}).get("TimePeriods", {}).get("Daily", []):
            if day.get("Date") == today:
                for t in day.get("Time", []):
                    type_ = t.get("Tide", "")
                    time_ = t.get("DateTime", "")[11:16]
                    height = t.get("TideHeights", {}).get("AboveChartDatum", "-")
                    tides.append(f"{type_} {time_} 潮高：{height} 公分")
        if not tides:
            return "今日無潮汐資料"
        return "今日潮汐預報：\n" + "\n".join(tides)
    except:
        return "潮汐資料讀取失敗"

def get_links():
    links = [
        ("韌性防災", "https://yliflood.yunlin.gov.tw/cameralist/#"),
        ("雲林路燈", "https://lamp.yunlin.gov.tw/slyunlin/Default.aspx"),
        ("管線挖掘", "https://pwd.yunlin.gov.tw/YLPub/"),
        ("台灣電力", "https://service.taipower.com.tw/nds/ndsWeb/ndft112.aspx"),
        ("停電查詢", "https://service.taipower.com.tw/branch/d120/xcnotice?xsmsid=0M242581310910082112"),
        ("自來水", "https://web.water.gov.tw/wateroff/"),
        ("氣象署官網", "https://www.cwa.gov.tw/V8/C/")
    ]
    msg = "常用連結：\n"
    for name, url in links:
        msg += f"{name}: {url}\n"
    return msg

@app.route("/webhook", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()

    if "天氣" in text:
        reply = fetch_weather()
    elif "颱風" in text:
        reply = fetch_typhoon()
    elif "地震" in text:
        reply = fetch_earthquake()
    elif "潮汐" in text:
        reply = fetch_tide()
    elif "連結" in text:
        reply = get_links()
    else:
        reply = ("您好！\n請輸入以下關鍵字查詢：\n"
                 "天氣、颱風、地震、潮汐、連結")

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    app.run(port=10000)
