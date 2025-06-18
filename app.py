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
    "3D CLEAR GLASS STICKER": "لزقه حمايه, لزقة حماية, لزقه شفاف",
    "3D Knit Pro Band For Whoop": "سير, سوار, ووب, سير خلق, سير قماش",
    "3D PRIAVCY GLASS STICKER": "لزقه حمايه, لزقة حماية, لزقه",
    "APEX": "لزقه كاميرا, حمايه كاميرا, حماية العدسات, ياقوت",
    "AR CAMERA STICKER": "لزقه كاميرا, حمايه كاميرا, حماية العدسات",
    "ARCO CARD CASE MagSafe Wallet Stand": "محفظة, مسكة المحفظه, مسكة حقة, حق البطايق, حق الكروت",
    "ARMOR CASE": "كفر, كفر جوال",
    "AROMA STAND AR-350": "مبخرة ستاند, حقة الملابس, مبخرة العامود",
    "AUTOVAC WIRELESS BRACKET CH-90": "قاعده سيارة, قاعده مغناطيس, قاعده شفط",
    "AVENTA STAND CASE": "كفر مع ستاند, كفر جوال, مسكة كفر",
    "CAR PHONE HOLDER": "قاعده سيارة, قاعده مغناطيس, قاعده, ماج سيف, مغناطيس",
    "CHYPRE CASE": "كفر, كفر جوال, كفر جوال ايفون",
    "CLEAR CRYSTAL CASE": "كفر, كفر جوال, كفر جوال ايفون, شفاف",
    "CRYSTAL MAGSAFE CASE": "كفر, كفر جوال, كفر جوال ايفون, شفاف, ماج سيف",
    "DUAL EARPHONE TYPE-C FOR IPHONE WHP-511": "سماعه صوبين, سماعة ايفون, تايب سي",
    "ELECTRIC HIRE TRIMMER": "ماكينة حلاقه, ماكينه حلاقة",
    "EXPLORER RING HOLDER": "مسكه, رنغ, رنج, خاتم",
    "FLABY CASE": "كفر, كفر جوال, كفر جوال ايفون, بلاستيك, نحيف, سليم, رقيق, مغشي",
    "FLEXGRIP MOUNT CAR HOLDER CH-35": "قاعده سيارة, قاعده مغناطيس, قاعده, قبقب",
    "Flaby Pro": "كفر, كفر جوال, كفر جوال ايفون, بلاستيك",
    "Gear Ring Holder": "مسكه, رنغ, رنج, خاتم, جير ستاند",
    "Grovix Case": "كفر, كفر جوال, كفر جوال ايفون",
    "Guard Shield Watch Case": "غطاء حمايه ساعة, حماية ساعة ابل",
    "Horizon Case": "كفر, كفر جوال, كفر جوال ايفون, كاربون",
    "I WATCH GLASS STICKER": "حمايه ساعة, حماية ساعة ابل",
    "Lavi steel Watch Band WB-260": "سير ساعة ابل, سير حديد, سير كروم, سير ساعة",
    "MAGGRIP PRO CAR HOLDER CH-40": "قاعده سيارة, قاعده مغناطيس, قاعده, راسية",
    "MAGNET CARD CASE": "محفظة, مسكة المحفظه, مسكة حقة, حق البطايق, حق الكروت",
    "Magic 4 Band Compatible With Whoop": "سير, سوار, ووب, سير خلق, سير قماش",
    "Magnetic Fast Wireless Charging Holder CH-60": "قاعده سيارة, قاعده مغناطيس, قاعده, ماج سيف, مغناطيس",
    "NANO MOUNT PRO CAR HOLDER CH-30": "قاعده سيارة, قاعده مغناطيس, قاعده",
    "NUVOLA SILICON CASE": "كفر, كفر جوال, كفر جوال ايفون, كفر سليكون",
    "Offroad Watch Band WB-340": "سير ساعة ابل, سير حديد, سير قماش, سير خلق",
    "Orbit Ring stand": "مسكه, رنغ, رنج, خاتm, حلقة",
    "PURE EDGE CLEAR 3D": "لزقه حمايه, لزقة حماية, لزقه شفاف, الفل",
    "PURE EDGE PRIVACY 3D": "لزقه حمايه, لزقة حماية, لزقه, برافسي, ملاقيف, كامل اطراف",
    "PURE MAG CASE": "كفر, كفر جوال, كفر جوال ايفون, بلاستيك ايسي, ما يصفر, ما يتغير لونه, شفاف",
    "Pop MAG Ring Holder": "مسكه, رنغ, رنج, خاتم, مسكه سليكون",
    "Pure Ring Mag": "كفر, كفر جوال, كفر جوال ايفون, بلاستيك ايسي, ما يصفر, ما يتغير لونه, شفاف",
    "Rindar Case – Matte Frosted Magnetic": "كفر, كفر جوال, كفر جوال ايفون",
    "SECUREGRIP CAR MOUNT CAR HOLDER CH-45": "قاعده سيارة, قاعده مغناطيس, قاعده",
    "SINGLE EARPHONE USB-C WHP-311": "سماعه صوب, سماعة ايفون, تايب سي, سماعة ايفون 15",
    "SINGLE HF MFI FOR IPHONE WHP-211": "سماعه صوب, سماعة ايفون, سماعة ايفون 14",
    "SMART AUTO CLIPPER CH-85": "قاعده سيارة, قاعده مغناطيس, قاعده",
    "SMART DIGITAL DISPLAY DATA CABLE C27L": "كيبل شحن, واير, وصلة لايتننغ, كيبل ايفون 14",
    "SMART DIGITAL DISPLAY DATA CABLE C55A": "كيبل شحن, واير, وصلة تايب سي, كيبل ايفون 15",
    "SMART DIGITAL DISPLAY DATA CABL C60C": "كيبل شحن, واير, وصلة تايب سي, كيبل ايفون 15",
    "SPINDO IPAD CASE": "كفر ايباد",
    "Silicon Band For Whoop Device": "سير, سوار, ووب, سير سليكون, سير ضد الماي",
    "Smart Aromatic Oasis with Built-in Laser Light AR-300": "مبخرة, معطر, حقة السيارة, مبخرة كهربائية, ليزر",
    "Smart Ember Burner EB-30": "مبخرة, حقة الفحم, مبخرة كهربائية",
    "TANDO RING HOLDER": "مسكه, رنغ, رنج, خاتم, حلقة, ستاند تاندو",
    "TITAN MAG PRO RING": "مسكه, رنغ, رنج, خاتم, حلقة, تيتان رنغ",
    "Thunder Case": "كفر, كفر جوال, كفر جوال ايفون, كفر مع مسكة",
    "VACUUM VORTEX BRACKET CH-80": "قاعده سيارة, قاعده مغناطيس, قاعده شفط, يدوي",
    "VIBE SHILED SERIES": "كفر, كفر جوال, كفر جوال ايفون, كاربون",
    "WATCH GLASS WITH FREAME": "حمايه ساعة, حماية ساعة ابل, مع فريم",
    "WIZARD MAGNET HEAD 22 RUBIDIUM STRONG MAGNETS N52 CH-65": "قاعده سيارة, قاعده مغناطيس, قاعده, راسية",
    "Watch Band Royal WB-200": "سير ساعة ابل, سير ساعة",
    "Wireless Vacuum Suction Phone Holder CH-95": "قاعده سيارة, قاعده مغناطيس, قاعده شفط, وايرليس",
    "Zeekr Silicon Band Watch Band WB-310": "سير ساعة ابل, سير ساعة, سير ساعة ابل سليكون",
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
        instructions,
        f"الكلمات المفتاحية للمنتجات:\n{json.dumps(PRODUCT_KEYWORDS, indent=2, ensure_ascii=False)}"
    ]
    
    # إضافة تاريخ المحادثة
    for msg in history:
        prompt_parts.append(f"{msg['role']}: {msg['parts'][0]}")
    
    # إضافة الرسالة الحالية
    prompt_parts.append(f"العميل أرسل: {message}")
    
    try:
        # إعداد المحتوى المرسل إلى Gemini
        contents = [{"text": "\n".join(prompt_parts)}]
        
        # إذا كان هناك صورة
        if image_url:
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            image_data = img_response.content
            
            # إضافة الصورة إلى المحتوى
            contents.append({"mime_type": "image/jpeg", "data": image_data})
        
        # إرسال كل المحتوى إلى Gemini
        response = model.generate_content(contents)
        
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
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload)
        if resp.status_code != 200:
            logging.error(f"Telegram send error: {resp.text}")
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

if __name__ == "__main__":
    # تحميل منتجات Shopify عند البدء
    refresh_shopify_cache()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))