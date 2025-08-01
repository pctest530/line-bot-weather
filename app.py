from flask import Flask, request, abort, render_template_string
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# ✅ 你的 LINE 憑證資訊 - 已更新為您提供的最新憑證
LINE_CHANNEL_ACCESS_TOKEN = "voGLDMSHC/Xfng1zq62Tn4pGDC2ZWwb7l+HrUj54NNqXy1SfAy3Bs/EKp64WLlwQaSQeomnS1JmIWCqugoovc9IxNQfp8vA1PNdxUpYanXVh/vEGAKb4yrufufYMhp+kGsT4fUx+I+HwNIzHTqqtbgdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "6362b12e044b913859b3772bf42cfa0d"
TO_USER_ID = "Uaaec86d0060844844df5bb2e731a375f" # 可選，用於啟動時推播訊息，若不需要可將此行註解或設為 None

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ✅ 氣象局金鑰 - 已更新為您提供的最新金鑰
CWA_API_KEY = "CWA-FA9ADF96-A21B-4D5D-9E9D-839DBF75AF71"

# 天氣圖示對應 (只定義一次)
ICON_MAP = {
    '晴': '☀️', '多雲': '⛅', '陰': '☁️',
    '短暫雨': '🌧️', '陣雨': '🌦️', '雷陣雨': '⛈️',
    '雨': '🌧️', '局部雨': '🌦️',
    '雷': '⚡', '有霧': '🌫️', '降雪': '❄️',
    '冰雹': '🧊', '霾': '😷'
}

# ✅ 首頁自動推播＋連結顯示
@app.route("/")
def home():
    if TO_USER_ID: # 只有在設定了 TO_USER_ID 才嘗試推播
        try:
            line_bot_api.push_message(
                TO_USER_ID,
                TextSendMessage(text="✅ LINE BOT 已啟動，請輸入：天氣、潮汐、颱風、地震、連結")
            )
        except Exception as e:
            # 在 Render 環境下，如果推播失敗通常是因為沒有 TO_USER_ID 或權限問題
            # 在首頁顯示錯誤，但不要阻擋程式運行
            print(f"❌ 推播失敗：{str(e)}")

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
        print("Invalid signature. Check your channel secret.")
        abort(400)
    except Exception as e:
        print(f"Error handling webhook: {e}")
        abort(500)
    return "OK"

# ✅ 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    user_id = event.source.user_id

    res = "請輸入：天氣、潮汐、颱風、地震 或 連結" # 預設回覆

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
    
    # 確保回覆的文字長度不超過 LINE 的限制 (通常是 2000 字元)
    if len(res) > 2000:
        res = res[:1990] + "..." # 截斷訊息，避免超出限制
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

# --- 天氣功能 ---
def get_weather_kouhu():
    """獲取口湖鄉 36 小時天氣預報"""
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}&locationName=雲林縣"
        response = requests.get(url, verify=False, timeout=10) # 增加 timeout
        response.raise_for_status() # 檢查 HTTP 請求是否成功
        data = response.json()
        
        # 檢查 records 和 location 是否存在
        records = data.get("records")
        if not records or not records.get("location"):
            return "❌ 天氣資料結構異常，請稍後再試。"
        
        loc = records["location"][0]
        wx_elements = loc.get("weatherElement")

        if not wx_elements:
            return "❌ 天氣資料元素遺失，請稍後再試。"

        # 找到需要的氣象元素 (使用字典推導式優化查找)
        elements_dict = {e["elementName"]: e["time"] for e in wx_elements}
        
        wx_times = elements_dict.get('Wx')
        pop_times = elements_dict.get('PoP')
        min_t_times = elements_dict.get('MinT')
        max_t_times = elements_dict.get('MaxT')

        if not all([wx_times, pop_times, min_t_times, max_t_times]):
            return "❌ 天氣預報資料不完整，請稍後再試。"

        labels = ['今早', '今晚', '明早']
        weather_info = "📍 口湖鄉 36 小時天氣預報：\n\n"

        # 確保迭代次數不超過最短的那個時間列表
        num_periods = min(len(wx_times), len(pop_times), len(min_t_times), len(max_t_times), 3)

        for i in range(num_periods):
            try:
                w_desc = wx_times[i]["parameter"]["parameterName"]
                pop_value = pop_times[i]["parameter"]["parameterName"]
                min_temp = min_t_times[i]["parameter"]["parameterName"]
                max_temp = max_t_times[i]["parameter"]["parameterName"]

                # 找出最符合的圖示
                icon = '❓'
                for key, val in ICON_MAP.items():
                    if key in w_desc:
                        icon = val
                        break
                
                # 處理時間格式，確保為 ISO 8601 格式
                start_time_str = wx_times[i]["startTime"]
                end_time_str = wx_times[i]["endTime"]

                start_time_obj = datetime.fromisoformat(start_time_str)
                end_time_obj = datetime.fromisoformat(end_time_str)
                
                start_time_formatted = start_time_obj.strftime("%m/%d %H:%M")
                end_time_formatted = end_time_obj.strftime("%H:%M") # 結束時間只顯示時分

                weather_info += (
                    f"▪️ {labels[i]} ({start_time_formatted}~{end_time_formatted})\n"
                    f"　天氣：{w_desc} {icon}\n"
                    f"　降雨機率：{pop_value}%\n"
                    f"　氣溫：{min_temp}°C ~ {max_temp}°C\n"
                )
                if i < num_periods - 1:
                    weather_info += "\n" # 每個時段之間加入換行
            except KeyError as ke:
                print(f"Weather data missing key: {ke} in period {i}")
                weather_info += f"▪️ {labels[i]} 資料不完整。\n\n"
            except Exception as e_inner:
                print(f"Error processing weather period {i}: {e_inner}")
                weather_info += f"▪️ {labels[i]} 處理錯誤。\n\n"

        return weather_info.strip() # 移除末尾多餘的換行和空格
    except requests.exceptions.RequestException as req_err:
        print(f"Network or API request error for weather: {req_err}")
        return f"❌ 取得天氣資料網路錯誤，請稍後再試。"
    except ValueError as val_err:
        print(f"JSON decoding error for weather: {val_err}")
        return f"❌ 天氣資料解析錯誤，請稍後再試。"
    except Exception as e:
        print(f"Unexpected error fetching weather: {e}")
        return f"❌ 取得天氣資料失敗，原因：{e}"


# --- 潮汐功能 ---
def get_tide_kouhu():
    """獲取口湖鄉潮汐預報（今日）"""
    LOCATION_ID = "10009190" # 口湖鄉
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001?Authorization={CWA_API_KEY}"
        response = requests.get(url, verify=False, timeout=10) # 增加 timeout
        response.raise_for_status() # 檢查 HTTP 請求是否成功
        data = response.json()

        if data.get("success") not in ["true", True]:
            print(f"Tide API success field is not true: {data.get('success')}")
            return "❌ 潮汐資料 API 回傳失敗。"

        records = data.get("records")
        if not records or not records.get("TideForecasts"):
            print("Tide data records or TideForecasts missing.")
            return "❌ 潮汐資料結構異常，請稍後再試。"

        forecasts = records["TideForecasts"]
        location_data = next((loc for loc in forecasts if loc["Location"]["LocationId"] == LOCATION_ID), None)

        if not location_data:
            return "找不到口湖鄉潮汐預報資料。"
        
        # 確保 TimePeriods 和 Daily 存在
        time_periods = location_data["Location"].get("TimePeriods")
        if not time_periods or not time_periods.get("Daily"):
            return "潮汐資料時間週期遺失。"

        all_daily_data = time_periods["Daily"]
        
        # 取得今天日期字串 (YYYY-MM-DD)
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 僅過濾今天的資料
        filtered_data = [d for d in all_daily_data if d["Date"] == today_str] # <--- 這裡已修改
        
        if not filtered_data:
            return "近期口湖鄉無潮汐資料。"

        tide_info_parts = []
        for day_data in filtered_data: # 現在這裡只會有今天的資料
            current_date_obj = datetime.strptime(day_data["Date"], "%Y-%m-%d")
            tide_info_parts.append(f"🌊 口湖鄉今日 ({current_date_obj.strftime('%m/%d')}) 潮汐預報：")

            if not day_data.get("Time"):
                tide_info_parts.append("　本日無潮汐事件。\n")
                continue

            for tide in day_data["Time"]:
                try:
                    tide_type = "退潮" if tide["Tide"] == "乾潮" else tide["Tide"]
                    
                    tide_time_str = tide["DateTime"]
                    tide_time_obj = datetime.fromisoformat(tide_time_str.replace("Z", "+00:00")) # 處理 Z 時區問題
                    tide_time_formatted = tide_time_obj.strftime("%H:%M")
                    
                    height = tide["TideHeights"].get("AboveChartDatum")
                    height_str = f"潮高：{height}公分" if height is not None else "潮高：-"

                    tide_info_parts.append(f"▪️ {tide_type}：{tide_time_formatted} ({height_str})")
                except KeyError as ke:
                    print(f"Tide data missing key: {ke}")
                    tide_info_parts.append(f"　部分潮汐資料不完整。")
                except ValueError as ve:
                    print(f"Error parsing tide datetime: {ve}")
                    tide_info_parts.append(f"　潮汐時間解析錯誤。")
                except Exception as e_inner:
                    print(f"Error processing tide event: {e_inner}")
                    tide_info_parts.append(f"　潮汐事件處理錯誤。")
            tide_info_parts.append("\n") # 每個日期區塊後加換行
        
        return "\n".join(tide_info_parts).strip() # 移除末尾多餘的換行和空格
    except requests.exceptions.RequestException as req_err:
        print(f"Network or API request error for tide: {req_err}")
        return f"❌ 取得潮汐資料網路錯誤，請稍後再試。"
    except ValueError as val_err:
        print(f"JSON decoding error for tide: {val_err}")
        return f"❌ 潮汐資料解析錯誤，請稍後再試。"
    except Exception as e:
        print(f"Unexpected error fetching tide: {e}")
        return f"❌ 取得潮汐資料失敗，原因：{e}"

# ✅ 颱風資料（API）
def get_typhoon():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0034-005?Authorization={CWA_API_KEY}"
        response = requests.get(url, verify=False, timeout=10)
        response.raise_for_status()
        r = response.json()
        
        typhoons = r.get("records", {}).get("tropicalCyclones", {}).get("tropicalCyclone", [])
        if not typhoons:
            return "📭 目前無活動颱風資訊。"
        
        latest = typhoons[0]
        name = latest.get("cwaTyphoonName", "未命名颱風")
        
        analysis_data = latest.get("analysisData")
        if not analysis_data or not analysis_data.get("fix"):
            return f"🌪️ 颱風：{name}，目前無詳細分析資料。"
            
        fix = analysis_data["fix"][0]
        
        fix_time_obj = datetime.fromisoformat(fix.get('fixTime', '')).strftime("%Y/%m/%d %H:%M") if fix.get('fixTime') else "未知時間"

        return (
            f"🌪️ 名稱：{name}\n"
            f"🕒 分析時間：{fix_time_obj}\n"
            f"📍 座標：{fix.get('coordinate', '未知')}\n"
            f"💨 風速：{fix.get('maxWindSpeed', '未知')} m/s\n"
            f"🎯 方向：{fix.get('movingDirection', '未知')}\n"
            f"🧭 速度：{fix.get('movingSpeed', '未知')} km/h\n"
            f"🎈 中心氣壓：{fix.get('pressure', '未知')} hPa"
        )
    except requests.exceptions.RequestException as req_err:
        print(f"Network or API request error for typhoon: {req_err}")
        return f"❌ 取得颱風資料網路錯誤，請稍後再試。"
    except ValueError as val_err:
        print(f"JSON decoding error for typhoon: {val_err}")
        return f"❌ 颱風資料解析錯誤，請稍後再試。"
    except Exception as e:
        print(f"Unexpected error fetching typhoon: {e}")
        return f"❌ 取得颱風資料失敗，原因：{e}"

# ✅ 地震資料（API）
def get_earthquake():
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={CWA_API_KEY}"
        response = requests.get(url, verify=False, timeout=10)
        response.raise_for_status()
        r = response.json()
        
        earthquakes = r.get("records", {}).get("Earthquake", [])
        if not earthquakes:
            return "📡 目前無顯著有感地震資料。"
        
        eq_info = earthquakes[0].get("EarthquakeInfo")
        if not eq_info:
            return "📡 無法取得地震詳細資訊。"

        origin_time_obj = datetime.fromisoformat(eq_info.get('OriginTime', '')).strftime("%Y/%m/%d %H:%M") if eq_info.get('OriginTime') else "未知時間"
        epicenter_loc = eq_info.get('Epicenter', {}).get('Location', '未知地點')
        magnitude_val = eq_info.get('EarthquakeMagnitude', {}).get('MagnitudeValue', '未知')
        focal_depth = eq_info.get('FocalDepth', '未知')

        return (
            f"📡 地震速報：\n"
            f"📍 地點：{epicenter_loc}\n"
            f"🕒 時間：{origin_time_obj}\n"
            f"📏 規模：{magnitude_val}，深度：{focal_depth} 公里"
        )
    except requests.exceptions.RequestException as req_err:
        print(f"Network or API request error for earthquake: {req_err}")
        return f"❌ 取得地震資料網路錯誤，請稍後再試。"
    except ValueError as val_err:
        print(f"JSON decoding error for earthquake: {val_err}")
        return f"❌ 地震資料解析錯誤，請稍後再試。"
    except Exception as e:
        print(f"Unexpected error fetching earthquake: {e}")
        return f"❌ 取得地震資料失敗，原因：{e}"

# ✅ 常用連結清單
def get_links():
    return [
        ("韌性防災", "https://yliflood.yunlin.gov.tw/cameralist/"),
        ("雲林路燈", "https://lamp.yunlin.gov.tw/slyunlin/Default.aspx"),
        ("管線挖掘", "https://pwd.yunlin.gov.tw/YLPub/"),
        ("台灣電力", "https://service.taipower.com.tw/nds/ndsWeb/ndft112.aspx"),
        ("停電查詢", "https://service.taipower.com.tw/branch/d120/xcnotice?xsmsid=0M242581310910082112"),
        ("自來水公司", "https://wateroff.water.gov.tw/"),
        ("氣象署資訊", "https://www.cwa.gov.tw/V8/C/")
        ("停班課查詢", "https://www.dgpa.gov.tw/typh/daily/nds.html"),
    ]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
