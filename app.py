from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# ✅ 用你自己的 Token 和 Secret
LINE_CHANNEL_ACCESS_TOKEN = "voGLDMSHC/Xfng1zq62Tn4pGDC2ZWwb7l+HrUj54NNqXy1SfAy3Bs/EKp64WLlwQaSQeomnS1JmIWCqugoovc9IxNQfp8vA1PNdxUpYanXVh/vEGAKb4yrufufYMhp+kGsT4fUx+I+HwNIzHTqqtbgdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "6362b12e044b913859b3772bf42cfa0d"

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/")
def home():
    return "✅ 抓 LINE 使用者 ID Bot 已上線"

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    msg = event.message.text.lower()

    if msg == "id":
        res = f"✅ 你的 LINE 使用者 ID 是：\n{user_id}"
    else:
        res = "請輸入 id，我會回傳你的 LINE 使用者 ID"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=res)
    )

if __name__ == "__main__":
    app.run()
