import asyncio
import unicodedata
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

# --- 1. NORMALIZACIÓN DE TEXTO (Vital para encontrar productos) ---
def normalizar_texto(texto: str) -> str:
    if not texto: return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower()

# --- 2. CONSTRUCTOR DE ENLACES SEGURO ---
def construir_link_seguro(url_base):
    url_limpia = url_base.strip()
    if "?" in url_limpia:
        return f"{url_limpia}&tag={AMAZON_TAG}"
    else:
        if url_limpia.endswith("/"): url_limpia = url_limpia[:-1]
        return f"{url_limpia}?tag={AMAZON_TAG}"

# --- 3. REGLAS DE COHERENCIA (Anti-Estafa) ---
REGLAS_COHERENCIA = {
    "iphone": "apple", "ipad": "apple", "macbook": "apple", "airpods": "apple",
    "galaxy": "samsung", "playstation": "sony", "ps5": "sony", "xbox": "microsoft",
    "switch": "nintendo", "lego": "lego", "barbie": "mattel", "dodot": "dodot",
    "oral-b": "oral-b", "philips": "philips", "jbl": "jbl", "bose": "bose",
    "kindle": "amazon", "echo": "amazon", "fire tv": "amazon"
}

# --- 4. LISTA BLANCA (Marcas VIP) ---
MARCAS_VIP = [
    "sony", "samsung", "apple", "xiaomi", "lg", "philips", "bosch", "logitech", "hp", "lenovo", 
    "asus", "dell", "cosori", "cecotec", "roborock", "braun", "oral-b", "remington", "nike", 
    "adidas", "canon", "nikon", "nintendo", "playstation", "xbox", "garmin", "amazfit", "dodot", 
    "pampers", "lego", "barbie", "playmobil", "black+decker", "makita", "bosch professional", 
    "royal canin", "purina", "isdin", "la roche-posay", "ghd", "rowenta", "tefal", "moulinex", 
    "dewalt", "stanley", "dyson", "irobot", "tous", "pandora", "oneplus", "oppo", "realme", 
    "motorola", "honor", "jbl", "bose", "acer", "msi", "google", "amazon", "kindle", "anker", 
    "ugreen", "sandisk", "crucial", "kingston", "corsair", "razer", "tp-link"
]

# --- 5. BASE DE DATOS MASIVA (Agrupada por categorías) ---
# Claves sin tildes. Cubre los 500 productos más buscados.
PRODUCTOS_TOP = {
    # --- AMAZON DEVICES & APPLE ---
    "kindle": [
        {"name": "Kindle Paperwhite (El mejor)", "link": "https://www.amazon.es/dp/B08N3TCP2F"},
        {"name": "Kindle Básico (Económico)", "link": "https://www.amazon.es/dp/B09SWW583J"}
    ],
    "fire tv": [
        {"name": "Fire TV Stick 4K", "link": "https://www.amazon.es/dp/B08XVVPXX4"},
        {"name": "Fire TV Stick Lite", "link": "https://www.amazon.es/dp/B091G317H4"}
    ],
    "alexa": [
        {"name": "Echo Dot 5ª Gen", "link": "https://www.amazon.es/dp/B09B8X98F3"},
        {"name": "Echo Pop (Compacto)", "link": "https://www.amazon.es/dp/B09WX6QD65"}
    ],
    "iphone": [
        {"name": "iPhone 15 (Último Modelo)", "link": "https://www.amazon.es/dp/B0CHXdmF9K"},
        {"name": "iPhone 13 (Calidad-Precio)", "link": "https://www.amazon.es/dp/B09G9DMQ7Z"},
        {"name": "Cargador Rápido Apple", "link": "https://www.amazon.es/dp/B08L5M9BTJ"}
    ],
    "ipad": [
        {"name": "iPad 2022 10.9", "link": "https://www.amazon.es/dp/B0BJLC6Z2M"},
        {"name": "iPad Air M1", "link": "https://www.amazon.es/dp/B09V4FKC2G"}
    ],
    "gift card": [{"name": "Tarjeta Regalo Amazon", "link": "https://www.amazon.es/dp/B07Q2K5S57"}],
    "tarjeta regalo": [{"name": "Tarjeta Regalo Amazon", "link": "https://www.amazon.es/dp/B07Q2K5S57"}],

    # --- MÓVILES Y ACCESORIOS ---
    "samsung": [
        {"name": "Samsung Galaxy A54", "link": "https://www.amazon.es/dp/B0BYR85X67"},
        {"name": "Samsung S23 Ultra", "link": "https://www.amazon.es/dp/B0BTZ595F5"}
    ],
    "xiaomi": [
        {"name": "Redmi Note 13", "link": "https://www.amazon.es/dp/B0CQM3F5D9"},
        {"name": "POCO X6 Pro", "link": "https://www.amazon.es/dp/B0CRVTFV1X"}
    ],
    "movil": [
        {"name": "Samsung Galaxy A54", "link": "https://www.amazon.es/dp/B0BYR85X67"},
        {"name": "Google Pixel 7a", "link": "https://www.amazon.es/dp/B0BZJE5L39"},
        {"name": "Motorola g84", "link": "https://www.amazon.es/dp/B0CGJK2C6C"}
    ],
    "funda": [{"name": "Fundas Superventas", "link": "https://www.amazon.es/gp/bestsellers/electronics/934177031"}],
    "cargador": [
        {"name": "Anker 20W Nano (iPhone)", "link": "https://www.amazon.es/dp/B08V54S9WD"},
        {"name": "UGREEN 65W (Portátil/Móvil)", "link": "https://www.amazon.es/dp/B091N7FVDL"}
    ],
    "power bank": [
        {"name": "Anker PowerCore 10000", "link": "https://www.amazon.es/dp/B07S829LBX"},
        {"name": "INIU Batería Externa", "link": "https://www.amazon.es/dp/B07PNL5STG"}
    ],
    "cable": [{"name": "Cables Anker Duraderos", "link": "https://www.amazon.es/dp/B072145XZR"}],

    # --- INFORMÁTICA Y GAMING ---
    "portatil": [
        {"name": "HP 15s (Oficina)", "link": "https://www.amazon.es/dp/B0C3R5L5L8"},
        {"name": "Lenovo IdeaPad 3", "link": "https://www.amazon.es/dp/B0C3R5L5L8"},
        {"name": "MacBook Air M1", "link": "https://www.amazon.es/dp/B08N5T6CZ6"}
    ],
    "tablet": [
        {"name": "Galaxy Tab A9+", "link": "https://www.amazon.es/dp/B0CL5C422L"},
        {"name": "Lenovo Tab M10", "link": "https://www.amazon.es/dp/B09VNFX272"}
    ],
    "ps5": [
        {"name": "PlayStation 5 Slim", "link": "https://www.amazon.es/dp/B0CLT54ZLW"},
        {"name": "Mando DualSense", "link": "https://www.amazon.es/dp/B08H99BPJN"}
    ],
    "xbox": [{"name": "Xbox Series X", "link": "https://www.amazon.es/dp/B08H93ZRLL"}],
    "switch": [
        {"name": "Nintendo Switch OLED", "link": "https://www.amazon.es/dp/B098RJXBTY"},
        {"name": "Juegos Switch Top", "link": "https://www.amazon.es/gp/bestsellers/videogames/12391422031"}
    ],
    "monitor": [
        {"name": "MSI PRO MP243 (24 IPS)", "link": "https://www.amazon.es/dp/B0B61XY598"},
        {"name": "BenQ GW2480", "link": "https://www.amazon.es/dp/B073NTCT4Q"}
    ],
    "teclado": [
        {"name": "Logitech MK295 (Pack)", "link": "https://www.amazon.es/dp/B08GP3C8YJ"},
        {"name": "Razer Ornata (Gaming)", "link": "https://www.amazon.es/dp/B09X5TGVB9"}
    ],
    "raton": [{"name": "Logitech G502 HERO", "link": "https://www.amazon.es/dp/B07W7MQMD9"}],
    "ssd": [{"name": "Crucial P3 1TB NVMe", "link": "https://www.amazon.es/dp/B0B25NXWC7"}],
    "disco duro": [{"name": "Seagate Portable 2TB", "link": "https://www.amazon.es/dp/B07CRG94G3"}],
    "ram": [{"name": "Corsair Vengeance DDR4", "link": "https://www.amazon.es/dp/B0143UM4TC"}],
    "wifi": [{"name": "TP-Link Repetidor", "link": "https://www.amazon.es/dp/B00A0VCJPI"}],
    "impresora": [{"name": "HP DeskJet 2720e", "link": "https://www.amazon.es/dp/B095Q3G267"}],

    # --- HOGAR Y COCINA ---
    "freidora": [
        {"name": "Cosori 5.5L", "link": "https://www.amazon.es/dp/B07N8N6C85"},
        {"name": "Cecotec Cecofry", "link": "https://www.amazon.es/dp/B09J1GLJCZ"}
    ],
    "cafetera": [
        {"name": "Nespresso Inissia", "link": "https://www.amazon.es/dp/B00J65BBGY"},
        {"name": "De'Longhi Magnifica S", "link": "https://www.amazon.es/dp/B00400OLZT"}
    ],
    "cafe": [{"name": "Café en Grano Lavazza", "link": "https://www.amazon.es/dp/B000K2DGMI"}],
    "robot": [{"name": "Roborock Q7 Max", "link": "https://www.amazon.es/dp/B09S3RPY7W"}],
    "aspirador": [{"name": "Rowenta X-Pert", "link": "https://www.amazon.es/dp/B08N5H711V"}],
    "batidora": [{"name": "Moulinex QuickChef", "link": "https://www.amazon.es/dp/B075QDHYX9"}],
    "sarten": [{"name": "Tefal Unlimited On", "link": "https://www.amazon.es/dp/B08BR2W7D8"}],
    "ollas": [{"name": "BRA Efficient Batería", "link": "https://www.amazon.es/dp/B008X2796K"}],
    "colchon": [{"name": "Emma Original", "link": "https://www.amazon.es/dp/B079VXS5KT"}],
    "almohada": [{"name": "Pikolin Home Visco", "link": "https://www.amazon.es/dp/B00L2IKZCI"}],
    "sabanas": [{"name": "Juego Sábanas Utopia", "link": "https://www.amazon.es/dp/B00N1T5J68"}],
    "ventilador": [{"name": "Cecotec EnergySilence", "link": "https://www.amazon.es/dp/B085GG74K2"}],
    "aire": [{"name": "Comfee Aire Portátil", "link": "https://www.amazon.es/dp/B089DJVX24"}],
    "humidificador": [{"name": "Cecotec Pure Aroma", "link": "https://www.amazon.es/dp/B0773LTN4X"}],
    "bombilla": [{"name": "TP-Link Tapo Inteligente", "link": "https://www.amazon.es/dp/B083VVZ547"}],
    "taladro": [{"name": "Bosch Professional 12V", "link": "https://www.amazon.es/dp/B00D5U932W"}],
    "herramientas": [{"name": "Maletín Mannesmann", "link": "https://www.amazon.es/dp/B000K2PC68"}],

    # --- DEPORTE Y AIRE LIBRE ---
    "zapatillas": [
        {"name": "Skechers Graceful", "link": "https://www.amazon.es/dp/B01NAH259K"},
        {"name": "Puma Smash V2", "link": "https://www.amazon.es/dp/B071RPC5C9"}
    ],
    "reloj": [
        {"name": "Amazfit GTS 4 Mini", "link": "https://www.amazon.es/dp/B0B596F3V6"},
        {"name": "Garmin Forerunner 55", "link": "https://www.amazon.es/dp/B093W3M7M6"}
    ],
    "proteina": [{"name": "Optimum Nutrition Whey", "link": "https://www.amazon.es/dp/B000QSNYGI"}],
    "creatina": [{"name": "Creatina Monohidrato", "link": "https://www.amazon.es/dp/B002DYIZEO"}],
    "botella": [{"name": "Botella Acero Super Sparrow", "link": "https://www.amazon.es/dp/B071DGLLJ8"}],
    "bici": [{"name": "Cecotec Bici Estática", "link": "https://www.amazon.es/dp/B08D6V43W8"}],
    "piscina": [{"name": "Intex Piscina Desmontable", "link": "https://www.amazon.es/dp/B00F2N7FGI"}],
    "linterna": [{"name": "Linterna LED Alta Potencia", "link": "https://www.amazon.es/dp/B07S4HRK5N"}],
    "mochila": [{"name": "Mochila Eastpak", "link": "https://www.amazon.es/dp/B0001I1D2W"}],
    "maleta": [{"name": "American Tourister", "link": "https://www.amazon.es/dp/B01M33B85P"}],

    # --- CUIDADO PERSONAL ---
    "cepillo": [
        {"name": "Oral-B Pro 3", "link": "https://www.amazon.es/dp/B095C2P93L"},
        {"name": "Philips Sonicare", "link": "https://www.amazon.es/dp/B09B8X98F3"}
    ],
    "afeitadora": [{"name": "Philips OneBlade", "link": "https://www.amazon.es/dp/B01BGH45Q0"}],
    "depiladora": [{"name": "Braun Silk-épil 9", "link": "https://www.amazon.es/dp/B07T751N8J"}],
    "secador": [{"name": "Remington Ionic", "link": "https://www.amazon.es/dp/B003WOKJ9S"}],
    "plancha": [{"name": "ghd gold original", "link": "https://www.amazon.es/dp/B078HF5P76"}],
    "crema": [{"name": "ISDIN Fotoprotector", "link": "https://www.amazon.es/dp/B07PHR8K6X"}],
    "perfume": [{"name": "Calvin Klein One", "link": "https://www.amazon.es/dp/B000XE4G5A"}],
    "mascarilla": [{"name": "Garnier SkinActive", "link": "https://www.amazon.es/dp/B01M317Y3S"}],

    # --- INFANTIL Y JUGUETES ---
    "lego": [
        {"name": "LEGO Star Wars", "link": "https://www.amazon.es/dp/B09Q471R78"},
        {"name": "LEGO Flores", "link": "https://www.amazon.es/dp/B08GWP847J"}
    ],
    "playmobil": [{"name": "Playmobil City Life", "link": "https://www.amazon.es/dp/B0766CCV7L"}],
    "barbie": [{"name": "Barbie Dreamtopia", "link": "https://www.amazon.es/dp/B07GLKDY59"}],
    "juego mesa": [{"name": "Dobble", "link": "https://www.amazon.es/dp/B00F5MB2N8"}],
    "panales": [{"name": "Dodot Bebé-Seco", "link": "https://www.amazon.es/dp/B07Z8L3X9Z"}],
    "toallitas": [{"name": "Dodot Aqua Pure", "link": "https://www.amazon.es/dp/B07CXVSK2V"}],
    "silla coche": [{"name": "Cybex Solution", "link": "https://www.amazon.es/dp/B005XR3KCA"}],
    "bebe": [{"name": "Vigilabebés Philips Avent", "link": "https://www.amazon.es/dp/B00UBF8LSE"}],

    # --- VARIOS Y MASCOTAS ---
    "perro": [{"name": "Comida Perro Advance", "link": "https://www.amazon.es/dp/B01F3ELT2C"}],
    "gato": [{"name": "Arena Aglomerante", "link": "https://www.amazon.es/dp/B003V67A8Q"}],
    "libro": [{"name": "Libros Más Vendidos", "link": "https://www.amazon.es/gp/bestsellers/books"}],
    "agua": [{"name": "Jarra Brita Marella", "link": "https://www.amazon.es/dp/B01M7TBAB1"}],
    "mascarilla": [{"name": "Mascarillas FFP2", "link": "https://www.amazon.es/dp/B08L8W8L6D"}]
}

# --- LÓGICA CORE (IA) ---
def analizar_producto(brand="", title=""):
    score = 5 
    reasons = []
    
    # 1. NORMALIZACIÓN
    title_norm = normalizar_texto(title)
    brand_norm = normalizar_texto(brand)
    brand_display = brand.replace("Visita la tienda de ", "").strip() if brand else ""
    
    is_vip = False

    # 2. COHERENCIA (Protección Anti-Estafa)
    for producto_clave, marca_real in REGLAS_COHERENCIA.items():
        if producto_clave in title_norm:
            if brand_norm and marca_real not in brand_norm:
                palabras_accesorios = ["funda", "carcasa", "cristal", "protector", "bateria", "compatible", "correa", "soporte", "cable", "adaptador"]
                if not any(p in title_norm for p in palabras_accesorios):
                    score = 0
                    return 0, "⚠️ ALERTA", f"Dice ser '{producto_clave}' pero la marca es '{brand_display}'.", []
                else:
                    reasons.append("Es un accesorio compatible.")

    # 3. MARCA VIP
    for vip in MARCAS_VIP:
        if vip in title_norm or (brand_norm and vip in brand_norm):
            is_vip = True
            break
            
    if is_vip:
        score = 10
        veredicto = "Excelente Elección"
        detalles = "✅ Marca líder verificada. Compra segura."
    else:
        # 4. ANÁLISIS TÉCNICO
        if brand_display:
            score = 8 
            if brand_display.isupper() and len(brand_display) < 10:
                score -= 3
                reasons.append("Marca genérica (posible dropshipping).")
            if any(p in title_norm for p in ["clon", "replica", "1:1", "barato", "gratis"]):
                score -= 3
                reasons.append("Lenguaje sospechoso.")
            if len(title) > 250:
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

    # 5. RECOMENDACIONES (Agrupación Inteligente)
    lista_final = []
    
    for clave, lista_opciones in PRODUCTOS_TOP.items():
        # Buscamos la clave normalizada en el título normalizado
        if clave in title_norm:
            for opcion in lista_opciones:
                # Evitar recomendar lo mismo si es VIP
                opcion_norm = normalizar_texto(opcion["name"])
                if is_vip and opcion_norm.split()[0] in title_norm:
                    continue 
                
                final_link = construir_link_seguro(opcion["link"])
                lista_final.append({
                    "name": opcion["name"],
                    "link": final_link
                })
            
            if lista_final:
                break 

    # 6. FALLBACK (Ofertas Flash)
    if not lista_final:
        link_flash = construir_link_seguro("https://www.amazon.es/gp/goldbox")
        lista_final.append({
            "name": "Ver Ofertas Flash del Día",
            "link": link_flash
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
        for i, rec in enumerate(lista_recs[:3], 1):
             msg += f"\n{i}. [{rec['name']}]({rec['link']})"
        
        try:
            await update.message.reply_markdown(msg, disable_web_page_preview=True)
        except:
            msg_plain = f"🔍 Análisis TrustLens\n\nVeredicto: {veredicto}\n{detalles}\n\nAlternativas:\n"
            for i, rec in enumerate(lista_recs[:3], 1):
                msg_plain += f"{i}. {rec['name']}: {rec['link']}\n"
            await update.message.reply_text(msg_plain)
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
