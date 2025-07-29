@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id  # ✅ 這行抓你的 LINE ID
    msg = event.message.text.strip()

    if msg == "id":
        res = f"✅ 你的 LINE 使用者 ID 是：\n{user_id}"
    elif msg == "天氣" or msg == "口湖天氣":
        res = get_weather()
    elif msg == "潮汐":
        res = get_tide()
    elif msg == "颱風":
        res = get_typhoon()
    elif msg == "地震":
        res = get_earthquake()
    else:
        res = "請輸入：天氣、潮汐、颱風、地震 或 id"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))
