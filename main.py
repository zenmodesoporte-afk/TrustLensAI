import asyncio
import unicodedata
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import html

# --- TUS CREDENCIALES ---
TELEGRAM_TOKEN = "7987693972:AAGL5lBHffpOjRjVodVcqqNK0XhTg-zFWRA"
AMAZON_TAG = "trustlens05-21"

app = FastAPI()

# Permisos para que la extensión de Chrome pueda hablar con el servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Product(BaseModel):
    title: str = ""
    brand: str = ""
    url: str = ""

# --- 1. NORMALIZACIÓN DE TEXTO ---
def normalizar_texto(texto: str) -> str:
    if not texto: return ""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower()

# --- 2. CONSTRUCTOR DE ENLACES PROFESIONAL ---
def construir_link_seguro(url_base):
    """
    Usa librerías de Python para inyectar el tag sin romper la URL.
    Funciona con cualquier tipo de enlace de Amazon.
    """
    try:
        # Limpiamos espacios
        url_base = url_base.strip()
        
        # Desmontamos la URL en piezas
        parsed = urlparse(url_base)
        
        # Leemos los parámetros actuales (si tiene ?k=iphone, etc)
        query_params = parse_qs(parsed.query)
        
        # Añadimos o sobreescribimos nuestro TAG
        query_params['tag'] = [AMAZON_TAG]
        
        # Reconstruimos la URL perfectamente
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        return new_url
    except Exception as e:
        print(f"Error construyendo link: {e}")
        # Fallback de emergencia por si acaso
        return f"https://www.amazon.es/?tag={AMAZON_TAG}"

# --- 3. REGLAS DE COHERENCIA ---
REGLAS_COHERENCIA = {
    "iphone": "apple", "ipad": "apple", "macbook": "apple", "airpods": "apple",
    "galaxy": "samsung", "playstation": "sony", "ps5": "sony", "xbox": "microsoft",
    "switch": "nintendo", "lego": "lego", "barbie": "mattel", "dodot": "dodot",
    "oral-b": "oral-b", "philips": "philips", "jbl": "jbl", "bose": "bose",
    "kindle": "amazon", "echo": "amazon", "fire tv": "amazon"
}

# --- 4. LISTA BLANCA ---
MARCAS_VIP = [
    "sony", "samsung", "apple", "xiaomi", "lg", "philips", "bosch", "logitech", "hp", "lenovo", 
    "asus", "dell", "cosori", "cecotec", "roborock", "braun", "oral-b", "remington", "nike", 
    "adidas", "canon", "nikon", "nintendo", "playstation", "xbox", "garmin", "amazfit", "dodot", 
    "pampers", "lego", "barbie", "playmobil", "black+decker", "makita", "bosch professional", 
    "royal canin", "purina", "isdin", "la roche-posay", "ghd", "rowenta", "tefal", "moulinex", 
    "dewalt", "stanley", "dyson", "irobot", "tous", "pandora", "oneplus", "oppo", "realme", 
    "motorola", "honor", "jbl", "bose", "acer", "msi", "google", "amazon", "kindle", "anker"
]

# --- 5. BASE DE DATOS OPTIMIZADA ---
PRODUCTOS_TOP = {
    "kindle": [{"name": "Kindle Paperwhite", "link": "https://www.amazon.es/dp/B08N3TCP2F"}],
    "iphone": [{"name": "iPhone 15", "link": "https://www.amazon.es/dp/B0CHXdmF9K"}, {"name": "iPhone 13", "link": "https://www.amazon.es/dp/B09G9DMQ7Z"}],
    "samsung": [{"name": "Samsung Galaxy A54", "link": "https://www.amazon.es/dp/B0BYR85X67"}],
    "xiaomi": [{"name": "Redmi Note 13", "link": "https://www.amazon.es/dp/B0CQM3F5D9"}],
    "portatil": [{"name": "HP 15s", "link": "https://www.amazon.es/dp/B0C3R5L5L8"}, {"name": "Lenovo IdeaPad", "link": "https://www.amazon.es/s?k=lenovo+ideapad"}],
    "laptop": [{"name": "HP 15s", "link": "https://www.amazon.es/dp/B0C3R5L5L8"}],
    "freidora": [{"name": "Cosori 5.5L", "link": "https://www.amazon.es/dp/B07N8N6C85"}],
    "air fryer": [{"name": "Cosori 5.5L", "link": "https://www.amazon.es/dp/B07N8N6C85"}],
    "cafetera": [{"name": "Nespresso Inissia", "link": "https://www.amazon.es/dp/B00J65BBGY"}],
    "auriculares": [{"name": "Sony WH-CH520", "link": "https://www.amazon.es/dp/B0BS1QCF54"}],
    "headphones": [{"name": "Sony WH-CH520", "link": "https://www.amazon.es/dp/B0BS1QCF54"}],
    "zapatillas": [{"name": "Skechers Graceful", "link": "https://www.amazon.es/dp/B01NAH259K"}, {"name": "Puma Smash", "link": "https://www.amazon.es/dp/B071RPC5C9"}],
    "sneakers": [{"name": "Skechers Graceful", "link": "https://www.amazon.es/dp/B01NAH259K"}],
    "lego": [{"name": "LEGO Star Wars", "link": "https://www.amazon.es/dp/B09Q471R78"}],
    "gift card": [{"name": "Tarjeta Regalo Amazon", "link": "https://www.amazon.es/dp/B07Q2K5S57"}]
}

# --- LÓGICA CORE (IA) ---
def analizar_producto(brand="", title=""):
    score = 5 
    reasons = []
    
    title_norm = normalizar_texto(title)
    brand_norm = normalizar_texto(brand)
    brand_display = brand.replace("Visita la tienda de ", "").strip() if brand else ""
    
    is_vip = False

    # 1. COHERENCIA
    for producto_clave, marca_real in REGLAS_COHERENCIA.items():
        if producto_clave in title_norm:
            if brand_norm and marca_real not in brand_norm:
                palabras_accesorios = ["funda", "carcasa", "cristal", "protector", "bateria", "compatible", "correa", "soporte", "cable", "adaptador", "case", "cover"]
                if not any(p in title_norm for p in palabras_accesorios):
                    score = 0
                    return 0, "⚠️ ALERTA", f"Dice ser '{producto_clave}' pero la marca es '{brand_display}'.", []
                else:
                    reasons.append("Es un accesorio compatible.")

    # 2. MARCA VIP
    for vip in MARCAS_VIP:
        if vip in title_norm or (brand_norm and vip in brand_norm):
            is_vip = True
            break
            
    if is_vip:
        score = 10
        veredicto = "Excelente Elección"
        detalles = "✅ Marca líder verificada. Compra segura."
    else:
        # 3. ANÁLISIS TÉCNICO
        if brand_display:
            score = 8 
            if brand_display.isupper() and len(brand_display) < 10:
                score -= 3
                reasons.append("Marca genérica (posible dropshipping).")
            if any(p in title_norm for p in ["clon", "replica", "1:1", "barato"]):
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

    # 4. RECOMENDACIONES
    lista_final = []
    
    for clave, lista_opciones in PRODUCTOS_TOP.items():
        if clave in title_norm:
            for opcion in lista_opciones:
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

    # 5. FALLBACK
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
    print(f"Recibida petición de extensión: {product.title}") # LOG PARA DEBUG
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
        
        # Escapamos caracteres HTML para evitar errores en Telegram
        veredicto_safe = html.escape(veredicto)
        detalles_safe = html.escape(detalles)

        msg = f"<b>🔍 Análisis TrustLens</b>\n\n📊 Veredicto: {veredicto_safe}\n📝 {detalles_safe}\n"
        msg += "\n💡 <b>Alternativas:</b>\n"
        
        for i, rec in enumerate(lista_recs[:3], 1):
             name_safe = html.escape(rec['name'])
             msg += f"\n{i}. <a href='{rec['link']}'>{name_safe}</a>"
        
        try:
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except Exception as e:
            print(f"Error enviando HTML a Telegram: {e}")
            await update.message.reply_text(f"Análisis: {veredicto}\n{detalles}\n\nRevisa las ofertas del día en Amazon.")
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
