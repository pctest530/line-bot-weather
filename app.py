from flask import Flask, request, abort, render_template_string
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests

app = Flask(__name__)

# ✅ 你的 LINE 憑證資訊
LINE_CHANNEL_ACCESS_TOKEN = "voGLDMSHC/Xfng1zq62Tn4pGDC2ZWwb7l+HrUj54NNqXy1SfAy3Bs/EKp64WLlwQaSQeomnS1JmIWCqugoovc9IxNQfp8vA1PNdxUpYanXVh/vEGAKb4yrufufYMhp+kGsT4fUx+I+HwNIzHTqqtbgdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "6362b12e044b913859b3772bf42cfa0d"
TO_USER_ID = "Uaaec86d0060844844df5bb2e731a375f"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ✅ 氣象局金鑰
CWA_API_KEY = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"

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
        res = "📍 口湖鄉 36 小時天氣預報：\nhttps://pctest530.github.io/weather/#weather"
    elif msg == "潮汐":
        res = "🌊 口湖鄉潮汐預報：\nhttps://pctest530.github.io/weather/#tide"
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
        fix = latest["analysisData"]["fix"][0]
        return (
            f"🌪️ 名稱：{name}\n📍 座標：{fix['coordinate']}\n"
            f"💨 風速：{fix['maxWindSpeed']} m/s\n🎯 方向：{fix['movingDirection']}\n"
            f"🧭 速度：{fix['movingSpeed']} km/h\n🎈 中心氣壓：{fix['pressure']} hPa"
        )
    except Exception as e:
        return f"❌ 颱風資料錯誤：{e}"

# ✅ 地震資料（API）
def get_earthquake():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={CWA_API_KEY}"
        r = requests.get(url, verify=False).json()
        eq = r["records"]["Earthquake"][0]["EarthquakeInfo"]
        return (
            f"📡 地震速報：\n📍 地點：{eq['Epicenter']['Location']}\n"
            f"🕒 時間：{eq['OriginTime']}\n📏 規模：{eq['EarthquakeMagnitude']['MagnitudeValue']}，深度：{eq['FocalDepth']} km"
        )
    except Exception as e:
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
    app.run()
