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
model = genai.GenerativeModel("gemini-1.5-flash")  # نموذج حديث يدعم الصور

# تعليمات النظام المعدلة
SYSTEM_INSTRUCTIONS = """
- أنا مساعد ذكي يعمل لدى شركة ورزد.
- لا أستخدم أي معلومات من خارج المتجر.
- إذا كتب العميل باللغة العربية، أرد باللهجة الخليجية. وإذا كتب بلغة إنجليزية أرد بلغة انجليزية.
- عند طلب منتج:
  - إذا كان الطلب عاماً (مثل: "أريد كفر")، أسأل العميل عن التفاصيل المطلوبة (نوع الكفر، لونه، مميزات إضافية).
  - عند الحصول على التفاصيل، أختار منتج واحد أو اثنين فقط من الأنسب للطلب.
  - أقدم المنتج مع رابط واحد فقط لكل منتج ووصف مختصر.
- أتصرف وكأني بشري 100٪: لا أجاوب إجابات آلية أو مختصرة بشكل غير مفهوم.
- أكون ودوداً ومفيداً في جميع الردود.
- لا أذكر أبداً أنني مساعد ذكي أو AI.
- في حالة وجود عدة منتجات، أختار الأفضل فقط ولا أذكر كل الخيارات.
- أستخدم الكلمات المفتاحية لمطابقة النية مع المنتجات.
- إذا أرسل العميل صورة، أحاول مطابقتها مع المنتجات.
"""

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
    "Orbit Ring stand": "مسكه, رنغ, رنج, خاتم, حلقة",
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

# ذاكرة المحادثة
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
    
    # الحفاظ على تاريخ المحادثة محدث (آخر 10 رسائل)
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
    # استرجاع تاريخ المحادثة (بدون الرسالة الحالية)
    history = conversation_history.get(chat_hash, [])[:-1]

    # جلب المنتجات من المتجر
    products = get_shopify_products()

    # فلترة المنتجات حسب الكلمات المفتاحية في الرسالة
    matched_products = []
    for p in products:
        keywords = PRODUCT_KEYWORDS.get(p["title"], "")
        if any(word.strip() in message for word in keywords.split(",")):
            matched_products.append(p)

    # تجهيز نص المنتجات المطابقة فقط
    if matched_products:
        shopify_products_text = "\n".join([
            f"- [{p['title']}]"
            f"(https://wizardch.com/products/{p['handle']})\n"
            f"  السعر: {p['variants'][0]['price']} ريال\n"
            f"  الوصف: {p['body_html']}"
            for p in matched_products if p.get("variants")
        ])
    else:
        shopify_products_text = "لا يوجد منتجات مطابقة للطلب حالياً."

    # بناء البرومبت
    prompt = f"""{SYSTEM_INSTRUCTIONS}

سجل المحادثة:
"""
    for msg in history:
        role = "العميل" if msg["role"] == "user" else "المساعد"
        content = msg['text']
        if msg.get('image'):
            content += " [صورة]"
        prompt += f"{role}: {content}\n"

    prompt += f"""

الكلمات المفتاحية للمنتجات:
{json.dumps(PRODUCT_KEYWORDS, indent=2, ensure_ascii=False)}

قائمة المنتجات من المتجر (اختر منها فقط المناسب للطلب):
{shopify_products_text}

رسالة العميل الحالية:
{message}
"""

    try:
        if image_url:
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            image_data = img_response.content

            gemini_response = model.generate_content(
                [
                    {"text": prompt},
                    {"mime_type": "image/jpeg", "data": image_data}
                ]
            )
        else:
            gemini_response = model.generate_content(prompt)

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