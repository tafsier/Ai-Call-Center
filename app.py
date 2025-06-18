from flask import Flask, request, jsonify
import os
import requests
from dotenv import load_dotenv
import google.generativeai as genai

# تحميل المتغيرات من .env
load_dotenv()
app = Flask(__name__)

# مفاتيح API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# تكوين Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    # التأكد من وجود رسالة
    if "message" not in data:
        return jsonify({"status": "no message"}), 200

    message_data = data["message"]
    chat_id = message_data["chat"]["id"]
    text = message_data.get("text", "")
    image_url = extract_image_url(message_data)  # ممكن تطويره لاحقًا

    # تحليل الرسالة عبر Gemini
    response_text = analyze_message_with_gemini(text, image_url)

    # الرد عبر تيليجرام
    send_telegram_message(chat_id, response_text)

    return jsonify({"status": "ok"}), 200


def analyze_message_with_gemini(message, image_url=None):
    prompt = f"""عميل أرسل:
{text if message else ""}
{f"رابط صورة: {image_url}" if image_url else ""}

ساعده بفهم المنتج الذي يسأل عنه من خلال الرسالة أو الصورة، وأخبره باسم المنتج أو الرابط أو السعر إن وُجد بالسياق."""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "حدث خطأ أثناء معالجة الطلب. يرجى المحاولة لاحقًا."


def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")


def extract_image_url(message_data):
    # حالياً لا يوجد دعم مباشر من Telegram لإرسال رابط الصورة في webhook
    # نتركها فارغة ونطورها لاحقًا عند استقبال الصور
    return None


if __name__ == "__main__":
   app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))