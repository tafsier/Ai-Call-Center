from flask import Flask, request, jsonify
import os
import requests
from dotenv import load_dotenv
import google.generativeai as genai
import logging
import json
import hashlib

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

# تعليمات النظام
SYSTEM_INSTRUCTIONS = """
- أنا مساعد ذكي يعمل لدى شركة ورزد.
- لا أستخدم أي معلومات من خارج المتجر.
- إذا كتب العميل باللغة العربية، أرد باللهجة الخليجية. وإذا كتب بلغة إنجليزية أرد بلغة انجليزية.
- عند طلب منتج، أستخدم الكلمات المفتاحية لمطابقة النية، ثم أجب بالرابط والوصف فقط.
- أتصرف وكأني بشري 100٪: لا أجاوب إجابات آلية أو مختصرة بشكل غير مفهوم.
- إذا أرسل العميل صورة او لينك، أعتبرها من الموقع وأحاول مطابقتها مع المنتجات.
- دائماً أكون ودوداً ومفيداً في جميع الردود.
"""

# تهيئة النموذج مع تعليمات النظام
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    system_instruction=SYSTEM_INSTRUCTIONS
)

# كلمات مفتاحية للمنتجات
PRODUCT_KEYWORDS = {
    "3D CLEAR GLASS STICKER": "لزقه حمايه, لزقة حماية, لزقه شفاف",
    # ... [بقية المنتجات كما هي] ...
    "Zeekr Silicon Band Watch Band WB-310": "سير ساعة ابل, سير ساعة, سير ساعة ابل سليكون",
}

# ذاكرة المحادثة (تخزين تاريخ المحادثة لكل مستخدم)
conversation_history = {}

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    if "message" not in data:
        return jsonify({"status": "no message"}), 200

    message_data = data["message"]
    chat_id = message_data["chat"]["id"]
    text = message_data.get("text", "") or message_data.get("caption", "")
    image_url = extract_image_url(message_data)
    
    # إنشاء معرف فريد للمحادثة
    chat_hash = hashlib.md5(str(chat_id).encode()).hexdigest()
    
    # استرجاع تاريخ المحادثة أو إنشاء جديد
    if chat_hash not in conversation_history:
        conversation_history[chat_hash] = []
    
    # إضافة رسالة المستخدم إلى التاريخ
    conversation_history[chat_hash].append({
        "role": "user",
        "text": text,
        "image": image_url
    })
    
    # تحليل الرسالة وإنشاء الرد
    response_text = analyze_message_with_gemini(chat_hash, text, image_url)
    
    # إضافة رد المساعد إلى التاريخ
    conversation_history[chat_hash].append({
        "role": "model",
        "text": response_text
    })
    
    # الحفاظ على تاريخ المحادثة محدث (آخر 5 تبادلات)
    if len(conversation_history[chat_hash]) > 10:
        conversation_history[chat_hash] = conversation_history[chat_hash][-10:]
    
    # إرسال الرد إلى المستخدم
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

def analyze_message_with_gemini(chat_hash, message, image_url=None):
    # استرجاع تاريخ المحادثة
    history = conversation_history.get(chat_hash, [])[:-1]  # استبعاد الرسالة الحالية
    
    # بناء محتوى المحادثة
    chat_content = []
    
    # إضافة التاريخ السابق
    for msg in history:
        parts = []
        
        if msg["role"] == "user":
            if msg["text"]:
                parts.append(msg["text"])
            if msg["image"]:
                try:
                    img_data = requests.get(msg["image"]).content
                    parts.append({
                        "mime_type": "image/jpeg",
                        "data": img_data
                    })
                except Exception as e:
                    logging.error(f"Failed to load history image: {e}")
        
        elif msg["role"] == "model":
            parts.append(msg["text"])
        
        if parts:
            chat_content.append({
                "role": msg["role"],
                "parts": parts
            })
    
    # إضافة الرسالة الحالية
    current_parts = []
    if message:
        current_parts.append(message)
    if image_url:
        try:
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            current_parts.append({
                "mime_type": "image/jpeg",
                "data": img_response.content
            })
        except Exception as e:
            logging.error(f"Current image error: {e}")
    
    chat_content.append({
        "role": "user",
        "parts": current_parts
    })
    
    # إضافة الكلمات المفتاحية
    chat_content.append({
        "role": "system",
        "parts": [f"الكلمات المفتاحية للمنتجات:\n{json.dumps(PRODUCT_KEYWORDS, indent=2, ensure_ascii=False)}"]
    })
    
    try:
        # إرسال المحادثة إلى Gemini
        response = model.generate_content(chat_content)
        return response.text.strip()
    
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