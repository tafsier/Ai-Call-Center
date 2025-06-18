from flask import Flask, request, jsonify
import os
import requests
from dotenv import load_dotenv
import google.generativeai as genai
import logging
import json

# تحميل متغيرات البيئة
load_dotenv()
app = Flask(__name__)

# مفاتيح API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")

# التحقق من وجود المفاتيح
if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise ValueError("API keys missing from environment variables")

# تهيئة Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")  # نموذج حديث يدعم الصور

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    if "message" not in data:
        return jsonify({"status": "no message"}), 200

    message_data = data["message"]
    chat_id = message_data["chat"]["id"]
    text = message_data.get("text", "") or message_data.get("caption", "")
    image_url = extract_image_url(message_data)

    response_text = analyze_message_with_gemini(text, image_url)
    send_telegram_message(chat_id, response_text)

    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def index():
    return "Service is running!", 200

def extract_image_url(message_data):
    # معالجة الصور المرفوعة مباشرة
    if 'photo' in message_data:
        photo_array = message_data['photo']
        file_id = photo_array[-1]['file_id']  # أعلى دقة
        return get_telegram_file_url(file_id)
    # معالجة الصور المرسلة كملف
    elif 'document' in message_data:
        doc = message_data['document']
        mime_type = doc.get('mime_type', '')
        if mime_type.startswith('image/'):
            return get_telegram_file_url(doc['file_id'])
    return None

def get_telegram_file_url(file_id):
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        )
        if response.status_code == 200:
            file_path = response.json()['result']['file_path']
            return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
    except Exception as e:
        logging.error(f"Telegram file error: {e}")
    return None

def analyze_message_with_gemini(message, image_url=None):
    prompt = f"العميل أرسل: {message}"
    try:
        if image_url:
            # تحميل بيانات الصورة
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            image_data = img_response.content

            # إرسال الصورة مع النص إلى Gemini
            gemini_response = model.generate_content(
                [
                    {"text": prompt},
                    {"mime_type": "image/jpeg", "data": image_data}
                ]
            )
        else:
            # إرسال النص فقط
            gemini_response = model.generate_content(prompt)

        # التأكد من وجود نص في الرد
        if hasattr(gemini_response, "text"):
            return gemini_response.text.strip()
        else:
            return "لم يتمكن النظام من توليد رد مناسب."

    except requests.exceptions.RequestException as e:
        logging.error(f"Image download error: {e}")
        return "حدث خطأ في تحميل الصورة أو معالجتها."
    except genai.types.BlockedPromptException:
        return "عذراً، المحتوى تم رفضه بواسطة نظام الأمان."
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return "حدث خطأ أثناء معالجة الطلب. يرجى المحاولة لاحقًا."

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(url, json=payload)
        if resp.status_code != 200:
            logging.error(f"Telegram send error: {resp.text}")
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

def get_shopify_products():
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2023-07/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("products", [])
    except Exception as e:
        logging.error(f"Shopify API error: {e}")
        return []

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))