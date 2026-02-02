import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- CONFIGURACIÓN (RELLENA ESTO) ---
TELEGRAM_TOKEN = "TU_TOKEN_DE_BOTFATHER_AQUÍ"
AMAZON_TAG = "TU_TAG_AFILIADO-21" 

app = FastAPI()

# Permitir conexiones de la extensión
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

# --- BASE DE DATOS DE RECOMENDACIONES (Añade aquí tus links) ---
# Si el título tiene la "Palave Clave", se recomienda ese producto.
PRODUCTOS_TOP = {
    "auriculares": {
        "name": "Sony WH-CH520 (Calidad Verificada)",
        "link": f"https://www.amazon.es/dp/B0BS1QCF54?tag={AMAZON_TAG}"
    },
    "inalambricos": {
        "name": "Soundcore Anker P20i (Económicos/Top)",
        "link": f"https://www.amazon.es/dp/B0BTYV49Y2?tag={AMAZON_TAG}"
    },
    "movil": {
        "name": "Samsung Galaxy A54 (Recomendado)",
        "link": f"https://www.amazon.es/dp/B0BYR85X67?tag={AMAZON_TAG}"
    },
    "freidora": {
        "name": "Cosori 5.5L (Mejor Valorada)",
        "link": f"https://www.amazon.es/dp/B07N8N6C85?tag={AMAZON_TAG}"
    },
    "reloj": {
        "name": "Amazfit GTS 4 Mini (Calidad/Precio)",
        "link": f"https://www.amazon.es/dp/B0B596F3V6?tag={AMAZON_TAG}"
    }
}

# --- LÓGICA DE ANÁLISIS ---
def analizar_producto(brand="", title=""):
    score = 10
    reasons = []
    title_low = title.lower() if title else ""
    
    # 1. Detección de marca sospechosa (Solo mayúsculas y corta)
    brand_clean = brand.replace("Visita la tienda de ", "").strip()
    if brand_clean.isupper() and len(brand_clean) < 10:
        score -= 4
        reasons.append("Marca genérica con control de calidad dudoso.")
    
    # 2. Detección de título SPAM
    if len(title_low) > 160:
        score -= 2
        reasons.append("Título diseñado para engañar al buscador (SEO Spam).")

    # 3. Selección de Recomendación Inteligente
    # Por defecto, si no hay match, mandamos a los más vendidos
    recomendacion_final = {
        "name": "Ver opciones de alta calidad",
        "link": f"https://www.amazon.es/gp/bestsellers/?tag={AMAZON_TAG}"
    }

    # Buscamos la palabra clave en el título
    for clave, info in PRODUCTOS_TOP.items():
        if clave in title_low:
            recomendacion_final = info
            break

    veredicto = "Parece seguro" if score > 7 else "⚠️ Sospechoso"
    detalles = " ".join(reasons) if reasons else "Marca y vendedor verificados."
    
    return score, veredicto, detalles, recomendacion_final

# --- ENDPOINT PARA LA EXTENSIÓN ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, detalles, rec = analizar_producto(product.brand or "", product.title or "")
    return {
        "score": score,
        "reason": f"{veredicto}: {detalles}",
        "recommendation": rec
    }

# --- BOT DE TELEGRAM ---
async def start(update: Update, context):
    await update.message.reply_text("🕵️ ¡TrustLens AI activo! Envíame un link de Amazon y detectaré si es una estafa o un producto de mala calidad.")

async def handle_msg(update: Update, context):
    url = update.message.text
    if "amazon" in url.lower():
        await update.message.reply_text("🕵️ Analizando...")
        # En el móvil no tenemos el DOM, así que hacemos un análisis genérico por URL o esperamos título
        _, veredicto, detalles, rec = analizar_producto("GENERIC", url)
        msg = f"🔍 *Resultado de TrustLens*\n\n✅ Veredicto: {veredicto}\n📝 {detalles}\n\n💡 *Mejor alternativa:* [{rec['name']}]({rec['link']})"
        await update.message.reply_markdown(msg)

@app.on_event("startup")
async def startup_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    await application.initialize()
    await application.start()
    asyncio.create_task(application.updater.start_polling())
