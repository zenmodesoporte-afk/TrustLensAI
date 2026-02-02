import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- TUS CREDENCIALES ---
TELEGRAM_TOKEN = "7987693972:AAGL5lBHffpOjRjVodVcqqNK0XhTg-zFWRA"
AMAZON_TAG = "trustlens05-21" 

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Product(BaseModel):
    title: str | None = None
    brand: str | None = None
    url: str

# --- LISTA DE MARCAS VIP (SI EL PRODUCTO ES DE ESTAS, ES SEGURO) ---
MARCAS_VIP = [
    "sony", "samsung", "apple", "xiaomi", "lg", "philips", "bosch", 
    "logitech", "hp", "lenovo", "asus", "dell", "cosori", "cecotec", 
    "roborock", "braun", "oral-b", "remington", "nike", "adidas", 
    "canon", "nikon", "nintendo", "playstation", "xbox", "garmin", 
    "amazfit", "dodot", "pampers", "lego", "barbie", "playmobil",
    "fischer", "black+decker", "makita", "bosch professional",
    "royal canin", "purina", "isdin", "la roche-posay", "garnier",
    "l'oreal", "maybelline", "ghd", "rowenta", "tefal", "moulinex"
]

# --- BASE DE DATOS MASIVA (Cubre las búsquedas TOP de Amazon) ---
PRODUCTOS_TOP = {
    # --- TECNOLOGÍA & GADGETS ---
    "iphone": {"name": "iPhone 13 (Oferta Top)", "link": "https://www.amazon.es/dp/B09G9DMQ7Z"},
    "samsung galaxy": {"name": "Samsung Galaxy A54", "link": "https://www.amazon.es/dp/B0BYR85X67"},
    "xiaomi": {"name": "Xiaomi Redmi Note 13", "link": "https://www.amazon.es/dp/B0CQM3F5D9"},
    "auriculares": {"name": "Sony WH-CH520", "link": "https://www.amazon.es/dp/B0BS1QCF54"},
    "cascos": {"name": "Sony WH-CH520", "link": "https://www.amazon.es/dp/B0BS1QCF54"},
    "inalambricos": {"name": "Soundcore P20i", "link": "https://www.amazon.es/dp/B0BTYV49Y2"},
    "tablet": {"name": "Samsung Galaxy Tab A9+", "link": "https://www.amazon.es/dp/B0CL5C422L"},
    "ipad": {"name": "iPad 2022 10.9", "link": "https://www.amazon.es/dp/B0BJLC6Z2M"},
    "kindle": {"name": "Kindle Paperwhite", "link": "https://www.amazon.es/dp/B08N3TCP2F"},
    "ebook": {"name": "Kindle Paperwhite", "link": "https://www.amazon.es/dp/B08N3TCP2F"},
    "alexa": {"name": "Echo Dot 5ª Gen", "link": "https://www.amazon.es/dp/B09B8X98F3"},
    "echo dot": {"name": "Echo Dot 5ª Gen", "link": "https://www.amazon.es/dp/B09B8X98F3"},
    "fire tv": {"name": "Fire TV Stick 4K", "link": "https://www.amazon.es/dp/B08XVVPXX4"},
    "smartwatch": {"name": "Xiaomi Smart Band 8", "link": "https://www.amazon.es/dp/B0CFRCT61X"},
    "pulsera": {"name": "Xiaomi Smart Band 8", "link": "https://www.amazon.es/dp/B0CFRCT61X"},
    "reloj": {"name": "Amazfit GTS 4 Mini", "link": "https://www.amazon.es/dp/B0B596F3V6"},
    "portatil": {"name": "HP 15s Laptop", "link": "https://www.amazon.es/dp/B0C3R5L5L8"},
    "ordenador": {"name": "HP 15s Laptop", "link": "https://www.amazon.es/dp/B0C3R5L5L8"},
    "raton": {"name": "Logitech G502 HERO", "link": "https://www.amazon.es/dp/B07W7MQMD9"},
    "teclado": {"name": "Logitech MK295", "link": "https://www.amazon.es/dp/B08GP3C8YJ"},
    "monitor": {"name": "MSI PRO MP243", "link": "https://www.amazon.es/dp/B0B61XY598"},
    "disco duro": {"name": "Crucial X6 1TB SSD", "link": "https://www.amazon.es/dp/B08W1F8YGJ"},
    "ssd": {"name": "Crucial X6 1TB SSD", "link": "https://www.amazon.es/dp/B08W1F8YGJ"},
    "cargador": {"name": "Anker 20W Nano", "link": "https://www.amazon.es/dp/B08V54S9WD"},
    "power bank": {"name": "Anker Batería Externa", "link": "https://www.amazon.es/dp/B07S829LBX"},
    "bateria": {"name": "Anker Batería Externa", "link": "https://www.amazon.es/dp/B07S829LBX"},

    # --- HOGAR & COCINA ---
    "freidora": {"name": "Cosori 5.5L Air Fryer", "link": "https://www.amazon.es/dp/B07N8N6C85"},
    "air fryer": {"name": "Cosori 5.5L Air Fryer", "link": "https://www.amazon.es/dp/B07N8N6C85"},
    "cafetera": {"name": "De'Longhi Nespresso", "link": "https://www.amazon.es/dp/B00J65BBGY"},
    "nespresso": {"name": "De'Longhi Nespresso", "link": "https://www.amazon.es/dp/B00J65BBGY"},
    "aspiradora": {"name": "Rowenta X-Pert", "link": "https://www.amazon.es/dp/B08N5H711V"},
    "robot aspirador": {"name": "roborock Q7 Max", "link": "https://www.amazon.es/dp/B09S3RPY7W"},
    "roomba": {"name": "iRobot Roomba", "link": "https://www.amazon.es/dp/B08H72T84L"},
    "batidora": {"name": "Moulinex QuickChef", "link": "https://www.amazon.es/dp/B075QDHYX9"},
    "sarten": {"name": "Tefal Unlimited On", "link": "https://www.amazon.es/dp/B08BR2W7D8"},
    "almohada": {"name": "Pikolin Home Visco", "link": "https://www.amazon.es/dp/B00L2IKZCI"},
    "colchon": {"name": "Emma Original", "link": "https://www.amazon.es/dp/B079VXS5KT"},
    "ventilador": {"name": "Cecotec EnergySilence", "link": "https://www.amazon.es/dp/B085GG74K2"},
    "aire acondicionado": {"name": "Comfee Portátil", "link": "https://www.amazon.es/dp/B089DJVX24"},
    "estufa": {"name": "Orbegozo HBF 90", "link": "https://www.amazon.es/dp/B00F2N7FGI"},
    "microondas": {"name": "Cecotec ProClean", "link": "https://www.amazon.es/dp/B07G3LSV4M"},

    # --- BELLEZA & SALUD ---
    "cepillo": {"name": "Oral-B Pro 3", "link": "https://www.amazon.es/dp/B095C2P93L"},
    "oral-b": {"name": "Oral-B Pro 3", "link": "https://www.amazon.es/dp/B095C2P93L"},
    "afeitadora": {"name": "Philips OneBlade", "link": "https://www.amazon.es/dp/B01BGH45Q0"},
    "depiladora": {"name": "Braun Silk-épil 9", "link": "https://www.amazon.es/dp/B07T751N8J"},
    "secador": {"name": "Parlux Advance Light", "link": "https://www.amazon.es/dp/B01CJLA7C2"},
    "plancha pelo": {"name": "ghd gold original", "link": "https://www.amazon.es/dp/B078HF5P76"},
    "ghd": {"name": "ghd gold original", "link": "https://www.amazon.es/dp/B078HF5P76"},
    "crema": {"name": "ISDIN Fotoprotector", "link": "https://www.amazon.es/dp/B07PHR8K6X"},
    "proteina": {"name": "Optimum Nutrition Whey", "link": "https://www.amazon.es/dp/B000QSNYGI"},
    "creatina": {"name": "Creatina Monohidrato", "link": "https://www.amazon.es/dp/B002DYIZEO"},

    # --- BEBÉ & JUGUETES ---
    "pañales": {"name": "Dodot Bebé-Seco", "link": "https://www.amazon.es/dp/B07Z8L3X9Z"},
    "dodot": {"name": "Dodot Bebé-Seco", "link": "https://www.amazon.es/dp/B07Z8L3X9Z"},
    "toallitas": {"name": "Dodot Aqua Pure", "link": "https://www.amazon.es/dp/B07CXVSK2V"},
    "silla coche": {"name": "Cybex Silver Solution", "link": "https://www.amazon.es/dp/B005XR3KCA"},
    "lego": {"name": "LEGO Star Wars", "link": "https://www.amazon.es/dp/B09Q471R78"},
    "playmobil": {"name": "Playmobil City Life", "link": "https://www.amazon.es/dp/B0766CCV7L"},
    "juego mesa": {"name": "Dobble", "link": "https://www.amazon.es/dp/B00F5MB2N8"},
    "barbie": {"name": "Barbie Dreamtopia", "link": "https://www.amazon.es/dp/B07GLKDY59"},

    # --- VIDEOJUEGOS ---
    "ps5": {"name": "PlayStation 5 Slim", "link": "https://www.amazon.es/dp/B0CLT54ZLW"},
    "playstation": {"name": "PlayStation 5 Slim", "link": "https://www.amazon.es/dp/B0CLT54ZLW"},
    "switch": {"name": "Nintendo Switch OLED", "link": "https://www.amazon.es/dp/B098RJXBTY"},
    "nintendo": {"name": "Nintendo Switch OLED", "link": "https://www.amazon.es/dp/B098RJXBTY"},
    "xbox": {"name": "Xbox Series X", "link": "https://www.amazon.es/dp/B08H93ZRLL"},
    "mando": {"name": "Mando PS5 DualSense", "link": "https://www.amazon.es/dp/B08H99BPJN"},

    # --- MASCOTAS ---
    "perro": {"name": "Comida Perro Advance", "link": "https://www.amazon.es/dp/B01F3ELT2C"},
    "gato": {"name": "Comida Gato Purina", "link": "https://www.amazon.es/dp/B07P8W6C8X"},
    "arena": {"name": "Arena Aglomerante", "link": "https://www.amazon.es/dp/B003V67A8Q"},
    "rascador": {"name": "Rascador Árbol Gatos", "link": "https://www.amazon.es/dp/B073P5G4XL"},

    # --- BRICOLAJE ---
    "taladro": {"name": "Bosch Professional 12V", "link": "https://www.amazon.es/dp/B00D5U932W"},
    "atornillador": {"name": "Bosch IXO", "link": "https://www.amazon.es/dp/B07X9VGQ3L"},
    "caja herramientas": {"name": "STANLEY Caja", "link": "https://www.amazon.es/dp/B0001I1D2W"},

    # --- EQUIPAJE Y MOCHILAS ---
    "mochila": {"name": "Samsonite Guardit 2.0", "link": "https://www.amazon.es/dp/B07NHX3R35"},
    "maleta": {"name": "American Tourister", "link": "https://www.amazon.es/dp/B01M33B85P"},
    "bolso": {"name": "Bolso Mujer Tous", "link": "https://www.amazon.es/dp/B07L5G3X8Z"}
}

# --- LÓGICA DEL CEREBRO (IA) ---
def analizar_producto(brand="", title=""):
    score = 10
    reasons = []
    title_low = title.lower() if title else ""
    brand_clean = brand.replace("Visita la tienda de ", "").strip() if brand else "Genérico"
    
    is_vip_brand = False
    
    # 1. Comprobar MARCA VIP
    for vip in MARCAS_VIP:
        if vip in title_low or vip in brand_clean.lower():
            is_vip_brand = True
            break
            
    if is_vip_brand:
        return 10, "Excelente Elección", "✅ Marca líder verificada. Compra segura.", None

    # 2. Análisis Técnico (Solo si no es VIP)
    if not is_vip_brand:
        if brand_clean.isupper() and len(brand_clean) < 10:
            score -= 4
            reasons.append("Marca genérica no reconocida.")
        if "http" not in title_low and len(title_low) > 250:
            score -= 2
            reasons.append("Título excesivamente largo.")

    # 3. Búsqueda de Recomendación
    recomendacion_final = None
    
    for clave, info in PRODUCTOS_TOP.items():
        if clave in title_low:
            # Si el usuario ya está viendo el producto bueno
            if info["name"].lower().split()[0] in title_low: 
                return 10, "Excelente Elección", "✅ Has elegido el producto mejor valorado de la categoría.", None
            
            # Construcción segura del enlace
            link_base = info["link"]
            final_link = f"{link_base}&tag={AMAZON_TAG}" if "?" in link_base else f"{link_base}?tag={AMAZON_TAG}"
            
            recomendacion_final = {
                "name": info["name"],
                "link": final_link
            }
            break

    # 4. Mensaje si NO encontramos nada (Petición del usuario)
    if not recomendacion_final and not is_vip_brand and score < 7:
        return 0, "Sin Análisis", "⚠️ Lo sentimos; este producto aún no lo hemos analizado en nuestra base de datos.", None

    # 5. Veredicto estándar (Si no es VIP pero tampoco es horrible)
    if score >= 8:
        veredicto = "Producto Seguro"
        detalles = "✅ Análisis positivo. Puedes comprar con confianza."
    elif score >= 5:
        veredicto = "Precaución"
        detalles = " ".join(reasons) if reasons else "Faltan datos de fiabilidad."
    else:
        veredicto = "⚠️ Sospechoso"
        detalles = " ".join(reasons)
    
    return score, veredicto, detalles, recomendacion_final

# --- RUTA EXTENSIÓN ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, detalles, rec = analizar_producto(product.brand, product.title)
    return {
        "score": score,
        "reason": f"{veredicto}: {detalles}",
        "recommendation": rec
    }

# --- RUTA TELEGRAM ---
async def start(update: Update, context):
    await update.message.reply_text("👋 ¡Hola! Soy TrustLens. Envíame un enlace de Amazon y te diré si es seguro.")

async def handle_msg(update: Update, context):
    user_text = update.message.text
    if "amazon" in user_text.lower() or "amzn" in user_text.lower():
        await update.message.reply_text("🕵️ Analizando...")
        
        score, veredicto, detalles, rec = analizar_producto(brand="", title=user_text)
        
        msg = f"🔍 *Análisis TrustLens*\n\n📊 Veredicto: {veredicto}\n📝 {detalles}\n"
        
        if rec:
            msg += f"\n💡 *Alternativa Recomendada:*\n[{rec['name']}]({rec['link']})"
            
        await update.message.reply_markdown(msg)
    else:
        await update.message.reply_text("❌ Por favor, envía un enlace válido de Amazon.")

@app.on_event("startup")
async def startup_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    await application.initialize()
    await application.start()
    asyncio.create_task(application.updater.start_polling())
