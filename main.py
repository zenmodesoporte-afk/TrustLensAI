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

# --- 1. REGLAS DE COHERENCIA (Protección Anti-Estafa) ---
REGLAS_COHERENCIA = {
    "iphone": "apple",
    "ipad": "apple",
    "airpods": "apple",
    "macbook": "apple",
    "galaxy": "samsung",
    "playstation": "sony",
    "ps5": "sony",
    "xbox": "microsoft",
    "switch": "nintendo",
    "lego": "lego",
    "barbie": "mattel",
    "dodot": "dodot",
    "oral-b": "oral-b",
    "philips": "philips"
}

# --- 2. LISTA BLANCA (Marcas VIP) ---
MARCAS_VIP = [
    "sony", "samsung", "apple", "xiaomi", "lg", "philips", "bosch", 
    "logitech", "hp", "lenovo", "asus", "dell", "cosori", "cecotec", 
    "roborock", "braun", "oral-b", "remington", "nike", "adidas", 
    "canon", "nikon", "nintendo", "playstation", "xbox", "garmin", 
    "amazfit", "dodot", "pampers", "lego", "barbie", "playmobil",
    "fischer", "black+decker", "makita", "bosch professional",
    "royal canin", "purina", "isdin", "la roche-posay", "garnier",
    "l'oreal", "maybelline", "ghd", "rowenta", "tefal", "moulinex",
    "dewalt", "stanley", "kärcher", "dyson", "irobot", "tous", "pandora",
    "oneplus", "oppo", "realme", "vivo", "motorola", "honor", "jbl", "bose"
]

# --- 3. BASE DE DATOS MASIVA (3 Opciones por Categoría) ---
# Cubre las palabras clave de los productos más vendidos en España.
PRODUCTOS_TOP = {
    # --- MÓVILES ---
    "iphone": [
        {"name": "iPhone 13 (Calidad/Precio)", "link": "https://www.amazon.es/dp/B09G9DMQ7Z"},
        {"name": "iPhone 15 (Último Modelo)", "link": "https://www.amazon.es/dp/B0CHXdmF9K"},
        {"name": "iPhone 12 (Económico)", "link": "https://www.amazon.es/dp/B08L5S963K"}
    ],
    "samsung": [
        {"name": "Samsung Galaxy A54 (Top Ventas)", "link": "https://www.amazon.es/dp/B0BYR85X67"},
        {"name": "Samsung S23 Ultra (Premium)", "link": "https://www.amazon.es/dp/B0BTZ595F5"},
        {"name": "Samsung Galaxy M13 (Barato)", "link": "https://www.amazon.es/dp/B09Z6M6M25"}
    ],
    "xiaomi": [
        {"name": "Xiaomi Redmi Note 13 (Recomendado)", "link": "https://www.amazon.es/dp/B0CQM3F5D9"},
        {"name": "POCO X6 Pro (Potencia Gamer)", "link": "https://www.amazon.es/dp/B0CRVTFV1X"},
        {"name": "Redmi 13C (Muy Barato)", "link": "https://www.amazon.es/dp/B0CMZFV6GY"}
    ],
    "movil": [ # Genérico
        {"name": "Samsung Galaxy A54", "link": "https://www.amazon.es/dp/B0BYR85X67"},
        {"name": "Google Pixel 7a (Mejor Cámara)", "link": "https://www.amazon.es/dp/B0BZJE5L39"},
        {"name": "Motorola g84 (Batería)", "link": "https://www.amazon.es/dp/B0CGJK2C6C"}
    ],

    # --- AUDIO ---
    "auriculares": [
        {"name": "Sony WH-CH520 (Calidad/Precio)", "link": "https://www.amazon.es/dp/B0BS1QCF54"},
        {"name": "Soundcore Q20i (Cancelación Ruido)", "link": "https://www.amazon.es/dp/B0C3HFE4X8"},
        {"name": "JBL Tune 510BT (Económicos)", "link": "https://www.amazon.es/dp/B08WM3LMJF"}
    ],
    "inalambricos": [
        {"name": "Soundcore P20i (Top Ventas)", "link": "https://www.amazon.es/dp/B0BTYV49Y2"},
        {"name": "Xiaomi Redmi Buds 4 (Baratos)", "link": "https://www.amazon.es/dp/B0C39X5R5B"},
        {"name": "AirPods Pro 2 (Premium)", "link": "https://www.amazon.es/dp/B0BDJBD317"}
    ],
    "altavoz": [
        {"name": "JBL Flip 6 (Sonido Top)", "link": "https://www.amazon.es/dp/B09V7D322V"},
        {"name": "Anker Soundcore 3 (Económico)", "link": "https://www.amazon.es/dp/B08B8PG37S"},
        {"name": "Ultimate Ears Wonderboom 3", "link": "https://www.amazon.es/dp/B09MKFFHBD"}
    ],

    # --- INFORMÁTICA ---
    "portatil": [
        {"name": "HP 15s (Oficina/Estudios)", "link": "https://www.amazon.es/dp/B0C3R5L5L8"},
        {"name": "Lenovo IdeaPad Slim 3 (Oferta)", "link": "https://www.amazon.es/dp/B0C3R5L5L8"},
        {"name": "MacBook Air M1 (Premium)", "link": "https://www.amazon.es/dp/B08N5T6CZ6"}
    ],
    "tablet": [
        {"name": "Samsung Galaxy Tab A9+ (Calidad)", "link": "https://www.amazon.es/dp/B0CL5C422L"},
        {"name": "Lenovo Tab M10 (Económica)", "link": "https://www.amazon.es/dp/B09VNFX272"},
        {"name": "iPad 10.9 (Apple)", "link": "https://www.amazon.es/dp/B0BJLC6Z2M"}
    ],
    "raton": [
        {"name": "Logitech G502 HERO (Gaming)", "link": "https://www.amazon.es/dp/B07W7MQMD9"},
        {"name": "Logitech M185 (Sencillo)", "link": "https://www.amazon.es/dp/B004YD8CPO"},
        {"name": "Logitech MX Master 3S (Pro)", "link": "https://www.amazon.es/dp/B0B11L5N11"}
    ],
    "monitor": [
        {"name": "MSI PRO MP243 (24\" IPS)", "link": "https://www.amazon.es/dp/B0B61XY598"},
        {"name": "BenQ GW2480 (Cuidado Ocular)", "link": "https://www.amazon.es/dp/B073NTCT4Q"},
        {"name": "LG 29WP500 (Ultrawide)", "link": "https://www.amazon.es/dp/B08XJSMZ6N"}
    ],

    # --- COCINA ---
    "freidora": [
        {"name": "Cosori 5.5L (La Nº1)", "link": "https://www.amazon.es/dp/B07N8N6C85"},
        {"name": "Cecotec Cecofry 6L (Barata)", "link": "https://www.amazon.es/dp/B09J1GLJCZ"},
        {"name": "Ninja Foodi (Doble Cesta)", "link": "https://www.amazon.es/dp/B09HZ22G1W"}
    ],
    "air fryer": [
        {"name": "Cosori 5.5L", "link": "https://www.amazon.es/dp/B07N8N6C85"},
        {"name": "Moulinex Easy Fry", "link": "https://www.amazon.es/dp/B07L5X2L56"}
    ],
    "cafetera": [
        {"name": "Nespresso Inissia (Cápsulas)", "link": "https://www.amazon.es/dp/B00J65BBGY"},
        {"name": "Cecotec Power Espresso (Barista)", "link": "https://www.amazon.es/dp/B07GSTVFJK"},
        {"name": "De'Longhi Magnifica S (Grano)", "link": "https://www.amazon.es/dp/B00400OLZT"}
    ],
    "batidora": [
        {"name": "Moulinex QuickChef (Potente)", "link": "https://www.amazon.es/dp/B075QDHYX9"},
        {"name": "Braun Minipimer 5200 (Clásica)", "link": "https://www.amazon.es/dp/B08KGT6D7Z"},
        {"name": "Cecotec Power Titanium (Vaso)", "link": "https://www.amazon.es/dp/B01N2Z1D2T"}
    ],
    "sarten": [
        {"name": "Tefal Unlimited On (Anti-rayas)", "link": "https://www.amazon.es/dp/B08BR2W7D8"},
        {"name": "BRA Efficient Orange (Lote)", "link": "https://www.amazon.es/dp/B003WOKJ9S"},
        {"name": "Monix M740040 (Económicas)", "link": "https://www.amazon.es/dp/B008X2796K"}
    ],

    # --- HOGAR ---
    "aspiradora": [
        {"name": "Roborock Q7 Max (Robot Top)", "link": "https://www.amazon.es/dp/B09S3RPY7W"},
        {"name": "Rowenta X-Pert (Escoba)", "link": "https://www.amazon.es/dp/B08N5H711V"},
        {"name": "Cecotec Conga 999 (Barato)", "link": "https://www.amazon.es/dp/B097C5R3M9"}
    ],
    "ventilador": [
        {"name": "Cecotec EnergySilence (Pie)", "link": "https://www.amazon.es/dp/B085GG74K2"},
        {"name": "Rowenta Turbo Silence (Silencioso)", "link": "https://www.amazon.es/dp/B01CJLA7C2"},
        {"name": "Honeywell TurboForce (Suelo)", "link": "https://www.amazon.es/dp/B003V67A8Q"}
    ],
    "almohada": [
        {"name": "Pikolin Home Visco", "link": "https://www.amazon.es/dp/B00L2IKZCI"},
        {"name": "Seasons Camaleón", "link": "https://www.amazon.es/dp/B079VXS5KT"}
    ],

    # --- CUIDADO PERSONAL ---
    "cepillo": [
        {"name": "Oral-B Pro 3 (Recomendado)", "link": "https://www.amazon.es/dp/B095C2P93L"},
        {"name": "Philips Sonicare (Sónico)", "link": "https://www.amazon.es/dp/B09B8X98F3"},
        {"name": "Oral-B iO 4 (Premium)", "link": "https://www.amazon.es/dp/B09XMTX6P2"}
    ],
    "afeitadora": [
        {"name": "Philips OneBlade (Cara/Cuerpo)", "link": "https://www.amazon.es/dp/B01BGH45Q0"},
        {"name": "Braun Series 5 (Eléctrica)", "link": "https://www.amazon.es/dp/B08H99BPJN"},
        {"name": "Philips Serie 5000 (Rápida)", "link": "https://www.amazon.es/dp/B087D2M3L3"}
    ],
    "depiladora": [
        {"name": "Braun Silk-épil 9 (Rápida)", "link": "https://www.amazon.es/dp/B07T751N8J"},
        {"name": "Philips Lumea (Luz Pulsada)", "link": "https://www.amazon.es/dp/B08H93ZRLL"},
        {"name": "Braun Silk-expert Pro 5 (IPL)", "link": "https://www.amazon.es/dp/B091CYX7F9"}
    ],
    "secador": [
        {"name": "Remington Ionic (Profesional)", "link": "https://www.amazon.es/dp/B003WOKJ9S"},
        {"name": "Parlux Advance (Alta Gama)", "link": "https://www.amazon.es/dp/B01CJLA7C2"},
        {"name": "Rowenta Powerline (Barato)", "link": "https://www.amazon.es/dp/B01CJLA7C2"}
    ],

    # --- OTROS (Bebé, Mascotas, Herramientas) ---
    "pañales": [
        {"name": "Dodot Bebé-Seco (Mensual)", "link": "https://www.amazon.es/dp/B07Z8L3X9Z"},
        {"name": "Dodot Aqua Pure (Toallitas)", "link": "https://www.amazon.es/dp/B07CXVSK2V"}
    ],
    "lego": [
        {"name": "LEGO Star Wars (Top)", "link": "https://www.amazon.es/dp/B09Q471R78"},
        {"name": "LEGO Technic (Coches)", "link": "https://www.amazon.es/dp/B09Q4N5Z3J"},
        {"name": "LEGO Flores (Decoración)", "link": "https://www.amazon.es/dp/B08GWP847J"}
    ],
    "taladro": [
        {"name": "Bosch Professional 12V", "link": "https://www.amazon.es/dp/B00D5U932W"},
        {"name": "Black+Decker (Hogar)", "link": "https://www.amazon.es/dp/B0114RJ7DG"},
        {"name": "Einhell Te-CD (Económico)", "link": "https://www.amazon.es/dp/B00B4UOTDQ"}
    ],
    "mochila": [
        {"name": "Samsonite Guardit 2.0", "link": "https://www.amazon.es/dp/B07NHX3R35"},
        {"name": "Eastpak Padded (Escolar)", "link": "https://www.amazon.es/dp/B0001I1D2W"},
        {"name": "HP Mochila (Portátil)", "link": "https://www.amazon.es/dp/B013TJX6W2"}
    ],
    "reloj": [
        {"name": "Amazfit GTS 4 Mini (Smart)", "link": "https://www.amazon.es/dp/B0B596F3V6"},
        {"name": "Casio G-SHOCK (Resistente)", "link": "https://www.amazon.es/dp/B000GAYQKY"},
        {"name": "Xiaomi Smart Band 8 (Pulsera)", "link": "https://www.amazon.es/dp/B0CFRCT61X"}
    ]
}

# --- LÓGICA CORE ---
def analizar_producto(brand="", title=""):
    score = 5 
    reasons = []
    title_low = title.lower() if title else ""
    brand_clean = brand.replace("Visita la tienda de ", "").strip() if brand else ""
    brand_low = brand_clean.lower()
    
    is_vip = False

    # 1. COHERENCIA (Anti-Fake)
    for producto_clave, marca_real in REGLAS_COHERENCIA.items():
        if producto_clave in title_low:
            if brand_clean and marca_real not in brand_low:
                # Excepción accesorios
                palabras_accesorios = ["funda", "carcasa", "cristal", "protector", "batería para", "compatible", "correa", "soporte"]
                if not any(p in title_low for p in palabras_accesorios):
                    score = 0
                    return 0, "⚠️ ALERTA", f"Dice ser '{producto_clave}' pero la marca es '{brand_clean}'. Posible réplica.", []
                else:
                    reasons.append("Es un accesorio compatible.")

    # 2. MARCA VIP
    for vip in MARCAS_VIP:
        if vip in title_low or (brand_clean and vip in brand_low):
            is_vip = True
            break
            
    if is_vip:
        score = 10
        veredicto = "Excelente Elección"
        detalles = "✅ Marca líder verificada. Compra segura."
    else:
        # 3. ANÁLISIS TÉCNICO
        if brand_clean:
            score = 8 
            if brand_clean.isupper() and len(brand_clean) < 10:
                score -= 3
                reasons.append("Marca genérica (posible dropshipping).")
            if any(p in title_low for p in ["clon", "réplica", "1:1", "barato"]):
                score -= 3
                reasons.append("Lenguaje sospechoso.")
            if len(title_low) > 250:
                score -= 1
        else:
            score = 5
            reasons.append("Análisis limitado (Solo enlace).")

    if score >= 8:
        veredicto = "Producto Seguro"
        detalles = "✅ Análisis positivo."
    elif score >= 5:
        veredicto = "Precaución"
        detalles = " ".join(reasons) if reasons else "Faltan datos."
    else:
        veredicto = "⚠️ Riesgo Alto"
        detalles = " ".join(reasons)

    # 4. RECOMENDACIONES (Generación de Links Segura)
    lista_final = []
    
    for clave, lista_opciones in PRODUCTOS_TOP.items():
        if clave in title_low:
            for opcion in lista_opciones:
                if is_vip and opcion["name"].lower().split()[0] in title_low:
                    continue 
                
                # --- CORRECCIÓN DE ENLACES ---
                # Usamos una lógica simple y sólida para evitar errores de URL
                base = opcion["link"]
                if "?" in base:
                    final_link = f"{base}&tag={AMAZON_TAG}"
                else:
                    final_link = f"{base}?tag={AMAZON_TAG}"
                
                lista_final.append({
                    "name": opcion["name"],
                    "link": final_link
                })
            
            if lista_final:
                break 

    # 5. SI NO HAY RESULTADOS, AÑADIMOS OFERTAS FLASH (Para que no falle la web)
    if not lista_final:
        lista_final.append({
            "name": "Aún no hemos verificado ese producto. Te animo a ver Ofertas Flash del Día",
            "link": f"https://www.amazon.es/gp/goldbox?tag={AMAZON_TAG}"
        })

    return score, veredicto, detalles, lista_final

# --- ENDPOINTS ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, detalles, lista_recs = analizar_producto(product.brand, product.title)
    return {
        "score": score,
        "reason": f"{veredicto}: {detalles}",
        "recommendation": lista_recs[0]
    }

async def start(update: Update, context):
    await update.message.reply_text("👋 Soy TrustLens. Envíame un enlace.")

async def handle_msg(update: Update, context):
    user_text = update.message.text
    if "amazon" in user_text.lower() or "amzn" in user_text.lower():
        await update.message.reply_text("🕵️ Analizando...")
        
        score, veredicto, detalles, lista_recs = analizar_producto(brand="", title=user_text)
        
        msg = f"🔍 *Análisis TrustLens*\n\n📊 Veredicto: {veredicto}\n📝 {detalles}\n"
        
        msg += "\n💡 *Alternativas:*\n"
        # Mostramos máximo 3 en Telegram
        for i, rec in enumerate(lista_recs[:3], 1):
             msg += f"\n{i}. [{rec['name']}]({rec['link']})"
        
        await update.message.reply_markdown(msg)
    else:
        await update.message.reply_text("❌ Enlace no válido.")

@app.on_event("startup")
async def startup_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    await application.initialize()
    await application.start()
    asyncio.create_task(application.updater.start_polling())
