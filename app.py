from flask import Flask, request, jsonify
import os
import requests
from dotenv import load_dotenv
import google.generativeai as genai
import logging
import json
import re
from datetime import datetime, timedelta

# تحميل متغيرات البيئة
load_dotenv()
app = Flask(__name__)

# مفاتيح API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")

# التحقق من وجود المفاتيح
if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN or not SHOPIFY_STORE_DOMAIN or not SHOPIFY_ACCESS_TOKEN:
    raise ValueError("API keys missing from environment variables")

# تهيئة Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")  # نموذج حديث يدعم السياق الطويل

# كلمات مفتاحية للمنتجات
PRODUCT_KEYWORDS = {
    # ... (نفس قاموس PRODUCT_KEYWORDS السابق)
}

# ذاكرة المحادثات
conversation_memory = {}
# مدة بقاء المحادثة في الذاكرة (ساعة واحدة)
MEMORY_EXPIRATION = timedelta(hours=1)

# ذاكرة منتجات Shopify
shopify_products_cache = []
CACHE_EXPIRATION = timedelta(minutes=30)
last_cache_update = datetime.min

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    
    if "message" not in data:
        return jsonify({"status": "no message"}), 200

    message_data = data["message"]
    chat_id = str(message_data["chat"]["id"])  # تحويل إلى نص للتخزين
    text = message_data.get("text", "") or message_data.get("caption", "")
    image_url = extract_image_url(message_data)
    
    # إنشاء ذاكرة جديدة إذا لزم الأمر
    if chat_id not in conversation_memory:
        conversation_memory[chat_id] = {
            "history": [],
            "created_at": datetime.now()
        }
    
    # تحديث الذاكرة
    conversation_memory[chat_id]["history"].append({"role": "user", "parts": [text]})
    
    # توليد الرد باستخدام تاريخ المحادثة
    response_text = analyze_message_with_gemini(chat_id, text, image_url)
    
    # إضافة رد المساعد للذاكرة
    conversation_memory[chat_id]["history"].append({"role": "model", "parts": [response_text]})
    
    # تنظيف الذاكرة القديمة
    cleanup_memory()
    
    send_telegram_message(chat_id, response_text)
    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def index():
    return "Service is running!", 200

def extract_image_url(message_data):
    # ... (نفس دالة extract_image_url السابقة)

def get_telegram_file_url(file_id):
    # ... (نفس دالة get_telegram_file_url السابقة)

def analyze_message_with_gemini(chat_id, message, image_url=None):
    # تعليمات المساعد الذكي
    instructions = """
    - أنا مساعد ذكي يعمل لدى شركة ورزد.
    - لا أستخدم أي معلومات من خارج المتجر.
    - إذا كتب العميل باللغة العربية، أرد باللهجة الخليجية. وإذا كتب بلغة إنجليزية أرد بلغة انجليزية.
    - عند طلب منتج، أستخدم الكلمات المفتاحية لمطابقة النية، ثم أجب باسم المنتج الدقيق ووصفه فقط.
    - أتصرف وكأني بشري 100٪: لا أجاوب إجابات آلية أو مختصرة بشكل غير مفهوم.
    - إذا أرسل العميل صورة او لينك، أعتبرها من الموقع وأحاول مطابقتها مع المنتجات.
    - عند ذكر منتج، أستخدم اسمه الدقيق كما في القاموس وأضعه بين علامتي <product></product>.
    """
    
    # جلب تاريخ المحادثة
    history = conversation_memory.get(chat_id, {"history": []})["history"]
    
    # إعداد البرومبت مع التاريخ والتعليمات
    prompt_parts = [
        {"text": instructions},
        {"text": f"الكلمات المفتاحية للمنتجات:\n{json.dumps(PRODUCT_KEYWORDS, indent=2, ensure_ascii=False)}"}
    ]
    
    # إضافة تاريخ المحادثة
    for msg in history:
        prompt_parts.append({"text": f"{msg['role']}: {msg['parts'][0]}"})
    
    # إضافة الرسالة الحالية
    prompt_parts.append({"text": f"العميل أرسل: {message}"})
    
    try:
        # إذا كان هناك صورة
        if image_url:
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            image_data = img_response.content
            
            # إضافة الصورة إلى البرومبت
            prompt_parts.append({"mime_type": "image/jpeg", "data": image_data})
        
        # إرسال كل المحتوى إلى Gemini
        response = model.generate_content(prompt_parts)
        
        # استخراج النص من الرد
        if hasattr(response, "text"):
            response_text = response.text.strip()
            
            # البحث عن أسماء المنتجات في الرد وإضافة روابط
            response_text = add_shopify_links(response_text)
            
            return response_text
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

def add_shopify_links(response_text):
    """استخراج أسماء المنتجات من الرد وإضافة روابط Shopify"""
    # البحث عن أسماء المنتجات بين علامتي <product>
    product_matches = re.findall(r'<product>(.*?)</product>', response_text)
    
    for product_name in product_matches:
        # البحث عن المنتج في Shopify
        product_url = find_product_url(product_name)
        
        if product_url:
            # استبدال اسم المنتج برابط
            response_text = response_text.replace(
                f'<product>{product_name}</product>',
                f'<a href="{product_url}">{product_name}</a>'
            )
    
    return response_text

def find_product_url(product_name):
    """البحث عن منتج في Shopify وإرجاع رابط المنتج"""
    try:
        # تحديث ذاكرة التخزين المؤقت إذا لزم الأمر
        refresh_shopify_cache()
        
        # البحث في ذاكرة التخزين المؤقت
        for product in shopify_products_cache:
            # البحث بمطابقة جزئية لاسم المنتج
            if product_name.lower() in product["title"].lower():
                return f"https://{SHOPIFY_STORE_DOMAIN}/products/{product['handle']}"
        
        # إذا لم يتم العثور على المنتج
        return None
    
    except Exception as e:
        logging.error(f"Product search error: {e}")
        return None

def refresh_shopify_cache():
    """تحديث ذاكرة تخزين منتجات Shopify"""
    global shopify_products_cache, last_cache_update
    
    # تحديث فقط إذا انتهت مدة التخزين المؤقت
    if datetime.now() - last_cache_update > CACHE_EXPIRATION:
        try:
            url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2023-07/products.json"
            headers = {
                "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # تحديث ذاكرة التخزين المؤقت
            shopify_products_cache = response.json().get("products", [])
            last_cache_update = datetime.now()
            logging.info(f"Shopify products cache updated. {len(shopify_products_cache)} products loaded.")
        
        except Exception as e:
            logging.error(f"Shopify cache update error: {e}")

def cleanup_memory():
    """تنظيف ذاكرة المحادثات القديمة"""
    current_time = datetime.now()
    expired_chats = []
    
    for chat_id, memory in conversation_memory.items():
        if current_time - memory["created_at"] > MEMORY_EXPIRATION:
            expired_chats.append(chat_id)
    
    for chat_id in expired_chats:
        del conversation_memory[chat_id]
        logging.info(f"Cleaned up memory for chat: {chat_id}")

def send_telegram_message(chat_id, text):
    # ... (نفس دالة send_telegram_message السابقة)

if __name__ == "__main__":
    # تحميل منتجات Shopify عند البدء
    refresh_shopify_cache()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))