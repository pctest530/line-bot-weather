from flask import Flask, request, abort, render_template_string
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
from datetime import datetime

app = Flask(__name__)

# LINE 憑證
LINE_CHANNEL_ACCESS_TOKEN = "voGLDMSHC/Xfng1zq62Tn4pGDC2ZWwb7l+HrUj54NNqXy1SfAy3Bs/EKp64WLlwQaSQeomnS1JmIWCqugoovc9IxNQfp8vA1PNdxUpYanXVh/vEGAKb4yrufufYMhp+kGsT4fUx+I+HwNIzHTqqtbgdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "6362b12e044b913859b3772bf42cfa0d"
TO_USER_ID = "Uaaec86d0060844844df5bb2e731a375f"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 氣象局金鑰
CWA_API_KEY = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"

# 首頁自動推播＋連結顯示
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

# webhook 接收點
@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    user_id = event.source.user_id

    if msg.lower() == "id":
        res = f"你的 LINE 使用者 ID 是：\n{user_id}"
    elif msg in ["天氣", "口湖天氣"]:
        res = get_weather()
    elif msg == "潮汐":
        res = get_tide()
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

# 取得天氣資料（口湖鄉36小時天氣）
def get_weather():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}&locationName=雲林縣"
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # 檢查 HTTP 狀態碼
        r = response.json()

        if "records" not in r or not r["records"].get("location"):
            return "❌ 無法取得天氣預報，可能是資料來源問題"
        
        loc = r["records"]["location"][0]
        weather_elements = {e['elementName']: e['time'] for e in loc['weatherElement']}

        icon_map = {
            '晴': '☀️', '多雲': '⛅', '陰': '☁️',
            '小雨': '🌧️','陣雨':'🌦️','雷陣雨':'⛈️',
            '雨':'🌧️','短暫陣雨':'🌦️','局部雨':'🌦️',
            '雷':'⚡'
        }

        labels = ['今早', '今晚', '明早']
        results = []
        for i in range(3):  # 取得未來 3 個時段資料
            wx = weather_elements['Wx'][i]['parameter']['parameterName']
            pop = weather_elements['PoP'][i]['parameter']['parameterName']
            min_t = weather_elements['MinT'][i]['parameter']['parameterName']
            max_t = weather_elements['MaxT'][i]['parameter']['parameterName']
            icon = next((v for k, v in icon_map.items() if k in wx), '❓')
            start = weather_elements['Wx'][i]['startTime'][5:16].replace('T', ' ')
            end = weather_elements['Wx'][i]['endTime'][11:16]

            results.append(f"{labels[i]} ({start}~{end}) {icon}\n天氣：{wx}\n降雨機率：{pop}%\n氣溫範圍：{min_t}°C ~ {max_t}°C")

        return "📍 口湖鄉 36 小時天氣預報：\n" + "\n\n".join(results)
    except Exception as e:
        return f"❌ 天氣資料錯誤：{e}"

# 取得潮汐資料（口湖鄉今日潮汐）
def get_tide():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={CWA_API_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        r = response.json()

        if "records" not in r or not r["records"].get("TideForecasts"):
            return "❌ 無法取得潮汐資料，可能是資料來源問題"

        location_id = "10009190"  # 口湖鄉
        forecasts = r["records"]["TideForecasts"]
        loc_data = next((loc for loc in forecasts if loc["Location"]["LocationId"] == location_id), None)

        if not loc_data:
            return "❌ 找不到口湖鄉的潮汐資料"

        today_str = datetime.now().strftime("%Y-%m-%d")
        daily = [d for d in loc_data["Location"]["TimePeriods"]["Daily"] if d["Date"] == today_str]

        if not daily:
            return "今日無潮汐資料"

        res_list = []
        for day in daily:
            for tide in day["Time"]:
                tide_type = tide["Tide"]
                if tide_type == "乾潮":
                    tide_type = "退潮"
                height = tide.get("TideHeights", {}).get("AboveChartDatum", "-")
                from datetime import datetime as dt
                dt_obj = dt.strptime(tide["DateTime"], "%Y-%m-%dT%H:%M:%S+08:00")
                hour = dt_obj.hour
                period = "上午" if hour < 12 else "下午"
                hour_12 = hour % 12 or 12
                minute = dt_obj.minute
                time_str = f"{period} {hour_12}:{minute:02d}"
                res_list.append(f"{day['Date']} {time_str} {tide_type} 潮 高度：{height}公分")

        return "🌊 口湖鄉今日潮汐預報：\n" + "\n".join(res_list)
    except Exception as e:
        return f"❌ 潮汐資料錯誤：{e}"

# 取得颱風資料
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

# 取得地震資料
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

# 常用連結
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
    app.run(host="0.0.0.0", port=5000, debug=True)
