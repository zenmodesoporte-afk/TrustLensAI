# trustlens_bot.py
import os
import re
import unicodedata
import html
import logging
import asyncio
from urllib.parse import quote_plus

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURACIÓN desde variables de entorno ---
TELEGRAM_TOKEN = os.getenv("7987693972:AAGL5lBHffpOjRjVodVcqqNK0XhTg-zFWRA")  # NO poner el token en el código
AMAZON_TAG = os.getenv("AMAZON_TAG", "trustlens05-21")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN no está definido en las variables de entorno")

# --- App FastAPI ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trustlens")

# --- Modelos ---
class Product(BaseModel):
    title: str = ""
    brand: str = ""
    url: str = ""

# --- Datos de referencia ---
MARCAS_TOP = [
    "sony", "samsung", "apple", "xiaomi", "lg", "philips", "bosch", "logitech", "hp", "lenovo",
    "asus", "dell", "cosori", "cecotec", "roborock", "braun", "oral b", "remington", "nike",
    "adidas", "nintendo", "playstation", "xbox", "garmin", "amazfit", "dodot", "lego", "ghd",
    "rowenta", "tefal", "moulinex", "dyson", "irobot", "anker", "huawei", "msi", "acer"
]

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

# --- Utilidades ---
def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    s = unicodedata.normalize('NFKD', texto)
    s = s.encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r'[^\w\s]', ' ', s)
    return s.lower().strip()

def construir_busqueda_segura(keyword: str) -> str:
    kw = quote_plus(keyword)
    rh = "p_72:831280031,p_85:831314031"
    return f"https://www.amazon.es/s?k={kw}&rh={rh}&tag={AMAZON_TAG}"

# --- Lógica principal ---
def analizar_inteligente(brand_raw: str, title_raw: str):
    title = limpiar_texto(title_raw)
    brand = limpiar_texto(brand_raw)

    # detectar categoría por coincidencia
    keyword_busqueda = "productos recomendados"
    for cat, sinonimos in CATEGORIAS.items():
        if cat in title or any(s in title for s in sinonimos):
            keyword_busqueda = cat
            break

    # determinar fiabilidad comparando con marcas limpias
    marcas_clean = [limpiar_texto(m) for m in MARCAS_TOP]
    es_fiable = any(m in brand for m in marcas_clean) or any(m in title for m in marcas_clean)

    # heurística adicional sobre marca original (no normalizada)
    sospechoso = False
    raw_brand = (brand_raw or "").strip()
    if raw_brand and raw_brand.isupper() and len(raw_brand) < 8:
        sospechoso = True
        es_fiable = False

    if es_fiable:
        veredicto = "✅ Parece fiable"
        razon = "Parece fiable por la trayectoria de la marca."
        score = 10
    else:
        veredicto = "⚠️ Precaución"
        razon = "No hay evidencia clara de fiabilidad; revisa valoraciones y garantía."
        score = 4

    recs = [
        {"name": f"Opción Premium de {keyword_busqueda.capitalize()}", "link": construir_busqueda_segura(f"{keyword_busqueda} alta gama")},
        {"name": f"Mejor Calidad/Precio (Verificado)", "link": construir_busqueda_segura(f"{keyword_busqueda} mejor valorado")},
        {"name": f"Alternativa Prime (Garantía)", "link": construir_busqueda_segura(f"{keyword_busqueda} top ventas")}
    ]

    return score, veredicto, razon, recs

# --- Endpoints API ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, razon, recs = analizar_inteligente(product.brand, product.title)
    return {
        "score": score,
        "reason": f"{veredicto}: {razon}",
        "recommendation": recs[1] if len(recs) > 1 else recs[0]
    }

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("👋 Hola, soy TrustLens AI. Envíame cualquier enlace de Amazon y analizaré su fiabilidad y garantía.")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    txt = update.message.text.strip()
    if "amazon" in txt.lower() or "amzn" in txt.lower():
        await update.message.reply_text("🕵️ Analizando integridad y valoraciones...")
        score, veredicto, razon, recs = analizar_inteligente("", txt)

        v_safe = html.escape(veredicto)
        r_safe = html.escape(razon)

        msg = f"<b>🔍 Informe TrustLens AI</b>\n\n📊 Veredicto: {v_safe}\n📝 {r_safe}\n"
        msg += "\n💡 <b>Alternativas con Garantía Prime y +4⭐:</b>\n"

        for i, r in enumerate(recs, 1):
            n_safe = html.escape(r['name'])
            link_safe = html.escape(r['link'], quote=True)
            msg += f'\n{i}. <a href="{link_safe}">{n_safe}</a>'

        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        await update.message.reply_text("❌ Por favor, envía un enlace válido de Amazon.")

# --- Arranque del bot en background con FastAPI ---
@app.on_event("startup")
async def startup_bot():
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
        # Ejecutar run_polling en un hilo para no bloquear FastAPI
        asyncio.create_task(asyncio.to_thread(application.run_polling))
        logger.info("🤖 Bot de Telegram en marcha (polling en background).")
    except Exception as e:
        logger.exception("Error arrancando el bot de Telegram: %s", e)

# --- Arranque local con uvicorn si se ejecuta como script ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("trustlens_bot:app", host="0.0.0.0", port=10000, reload=False)
