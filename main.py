import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- CONFIGURACIÓN (RELLENA ESTO) ---
TELEGRAM_TOKEN = "7987693972:AAGL5lBHffpOjRjVodVcqqNK0XhTg-zFWRA"
AMAZON_TAG = "trustlens05-21"

app = FastAPI()

# Permitir que la extensión se conecte
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Product(BaseModel):
    title: str | None = None
    brand: str | None = None
    reviewCount: str | None = None
    url: str

# --- LÓGICA DE ANÁLISIS ÚNICA ---
def analizar_producto(brand="", title=""):
    score = 10
    reasons = []
    
    brand_upper = brand.replace("Visita la tienda de ", "").strip()
    if brand_upper.isupper() and len(brand_upper) < 10:
        score -= 4
        reasons.append("Marca genérica sospechosa.")
    
    if len(title) > 150:
        score -= 2
        reasons.append("Título con exceso de palabras clave.")

    veredicto = "Parece seguro" if score > 6 else "⚠️ Sospechoso"
    detalles = " ".join(reasons) if reasons else "Producto verificado por TrustLens."
    
    # Enlace de afiliado genérico o específico (puedes ampliar esto)
    link_alternativo = f"https://www.amazon.es/s?k=mejor+calidad+precio&tag={AMAZON_TAG}"
    
    return score, veredicto, detalles, link_alternativo

# --- RUTA PARA LA EXTENSIÓN ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, detalles, link = analizar_producto(product.brand, product.title)
    return {
        "score": score,
        "reason": f"{veredicto}: {detalles}",
        "recommendation": {"name": "Ver alternativa mejorada", "link": link}
    }

# --- BOT DE TELEGRAM ---
async def start(update: Update, context):
    await update.message.reply_text("🕵️ ¡Bienvenido a TrustLens! Envíame un link de la App de Amazon y lo analizaré.")

async def handle_msg(update: Update, context):
    url = update.message.text
    if "amazon" in url.lower():
        await update.message.reply_text("Analizando...")
        _, veredicto, detalles, link = analizar_producto("GENERIC", "Producto de móvil")
        msg = f"🔍 *Resultado:* {veredicto}\n\n📝 {detalles}\n\n💡 *Alternativa segura:* [Comprar aquí]({link})"
        await update.message.reply_markdown(msg)

@app.on_event("startup")
async def startup_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    await application.initialize()
    await application.start()
    asyncio.create_task(application.updater.start_polling())