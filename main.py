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

# --- CONFIGURACIÓN ---
TELEGRAM_TOKEN = "7987693972:AAGL5lBHffpOjRjVodVcqqNK0XhTg-zFWRA"
AMAZON_TAG = "trustlens05-21"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Product(BaseModel):
    title: str = ""
    brand: str = ""
    url: str = ""

# --- UTILIDADES ---
def normalizar(texto: str) -> str:
    if not texto: return ""
    # Quita tildes, convierte a minúsculas y limpia espacios
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower().strip()

def construir_busqueda_segura(keyword: str) -> str:
    """Genera un link de Amazon filtrado por 4+ estrellas y Prime (Garantía)"""
    # Filtros: p_72 (4+ estrellas) y p_85 (Prime)
    params = {
        "k": keyword,
        "rh": "p_72:831280031,p_85:831314031",
        "tag": AMAZON_TAG
    }
    return f"https://www.amazon.es/s?{urlencode(params)}"

# --- BASE DE DATOS DE MARCAS FIABLES ---
MARCAS_TOP = [
    "sony", "samsung", "apple", "xiaomi", "lg", "philips", "bosch", "logitech", "hp", "lenovo", 
    "asus", "dell", "cosori", "cecotec", "roborock", "braun", "oral-b", "remington", "nike", 
    "adidas", "nintendo", "playstation", "xbox", "garmin", "amazfit", "dodot", "lego", "ghd", 
    "rowenta", "tefal", "moulinex", "dyson", "irobot", "anker", "huawei", "msi", "acer"
]

# --- DICCIONARIO DE CATEGORÍAS (Para recomendaciones inteligentes) ---
CATEGORIAS = {
    "auriculares": ["headphones", "cascos", "airpods", "earbuds"],
    "portatil": ["laptop", "ordenador", "macbook"],
    "movil": ["smartphone", "telefono", "iphone", "galaxy"],
    "freidora": ["air fryer", "cosori", "freidora sin aceite"],
    "reloj": ["smartwatch", "reloj inteligente", "garmin", "apple watch"],
    "aspirador": ["conga", "roborock", "roomba", "aspiradora"],
    "teclado": ["keyboard", "teclado mecanico"],
    "zapatillas": ["sneakers", "zapatos deportivos", "nike", "adidas"]
}

# --- LÓGICA DE ANÁLISIS ---
def analizar_inteligente(brand_raw, title_raw):
    title = normalizar(title_raw)
    brand = normalizar(brand_raw)
    
    # 1. Detectar qué producto es para buscar similares
    keyword_busqueda = "productos recomendados"
    for cat, sinonimos in CATEGORIAS.items():
        if cat in title or any(s in title for s in sinonimos):
            keyword_busqueda = cat
            break

    # 2. Determinar fiabilidad
    # Caso A: Marca VIP o Título con Marca VIP
    es_fiable = any(m in brand or m in title for m in MARCAS_TOP)
    
    # Si la marca es sospechosa (Todo mayúsculas, corta, etc.)
    if not es_fiable and brand.isupper() and len(brand) < 8:
        es_fiable = False

    # 3. Construir Respuesta según tu solicitud
    if es_fiable:
        veredicto = "✅ Parece fiable"
        razon = "Lo sentimos, aún no hemos evaluado este producto; pero parece fiable por la trayectoria de la marca."
        score = 10
    else:
        veredicto = "⚠️ Precaución"
        razon = "Lo sentimos, aún no hemos evaluado este producto; pero le aconsejamos visitar estos productos similares con mejores garantías."
        score = 4

    # 4. Generar 3 Alternativas Reales con Filtro de Garantía
    recs = [
        {"name": f"Opción Premium de {keyword_busqueda.capitalize()}", "link": construir_busqueda_segura(f"{keyword_busqueda} alta gama")},
        {"name": f"Mejor Calidad/Precio (Verificado)", "link": construir_busqueda_segura(f"{keyword_busqueda} mejor valorado")},
        {"name": f"Alternativa Prime (Garantía)", "link": construir_busqueda_segura(f"{keyword_busqueda} top ventas")}
    ]
    
    return score, veredicto, razon, recs

# --- API ENDPOINTS ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, razon, recs = analizar_inteligente(product.brand, product.title)
    return {
        "score": score,
        "reason": f"{veredicto}: {razon}",
        "recommendation": recs[1] # Opción central para la extensión
    }

# --- TELEGRAM BOT ---
async def start(update: Update, context):
    await update.message.reply_text("👋 Hola, soy TrustLens AI. Envíame cualquier enlace de Amazon y analizaré su fiabilidad y garantía.")

async def handle_msg(update: Update, context):
    txt = update.message.text
    if "amazon" in txt.lower() or "amzn" in txt.lower():
        await update.message.reply_text("🕵️ Analizando integridad y valoraciones...")
        
        # En Telegram a veces solo tenemos el título/link, el bot lo analiza
        score, veredicto, razon, recs = analizar_inteligente("", txt)
        
        v_safe = html.escape(veredicto)
        r_safe = html.escape(razon)

        msg = f"<b>🔍 Informe TrustLens AI</b>\n\n📊 Veredicto: {v_safe}\n📝 {r_safe}\n"
        msg += "\n💡 <b>Alternativas con Garantía Prime y +4⭐:</b>\n"
        
        for i, r in enumerate(recs, 1):
            n_safe = html.escape(r['name'])
            msg += f"\n{i}. <a href='{r['link']}'>{n_safe}</a>"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        await update.message.reply_text("❌ Por favor, envía un enlace válido de Amazon.")

@app.on_event("startup")
async def startup_bot():
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
        await application.initialize()
        await application.start()
        asyncio.create_task(application.updater.start_polling(drop_pending_updates=True))
        print("🤖 Bot de Telegram en marcha...")
    except Exception as e:
        print(f"⚠️ Error bot: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
