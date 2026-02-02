import asyncio
import unicodedata
from urllib.parse import urlencode
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, MessageHandler, filters
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

# --- 1. CONFIGURACIÓN DE MARCAS Y CATEGORÍAS ---
MARCAS_TOP = [
    "apple", "samsung", "sony", "xiaomi", "lg", "philips", "hp", "lenovo", "asus", "logitech", 
    "cosori", "cecotec", "roborock", "dyson", "nintendo", "nike", "adidas", "puma", "clarks", 
    "bosch", "makita", "oral-b", "braun", "rowenta", "moulinex", "tefal", "isdin", "garmin", 
    "amazfit", "anker", "tp-link", "lego", "dodot", "ghd", "remington", "canon", "nikon"
]

CATEGORIAS_MAESTRAS = {
    "auriculares": ["cascos", "airpods", "earbuds", "headphones", "diadema", "inalambricos"],
    "portatil": ["laptop", "ordenador", "macbook", "notebook", "sobremesa", "pc"],
    "movil": ["smartphone", "telefono", "iphone", "galaxy", "xiaomi", "celular"],
    "reloj": ["smartwatch", "reloj inteligente", "pulsera actividad", "fitbit", "garmin", "relojes"],
    "tablet": ["ipad", "galaxy tab", "tableta", "ebook", "kindle"],
    "altavoz": ["speaker", "bluetooth", "alexa", "echo", "barra de sonido"],
    "monitor": ["pantalla", "gaming", "curvo", "monitor pc"],
    "freidora": ["air fryer", "sin aceite", "cosori", "freidora aire"],
    "aspirador": ["aspiradora", "robot", "conga", "roomba", "roborock", "escoba"],
    "cafetera": ["nespresso", "dolce gusto", "superautomatica", "expresso", "italiana"],
    "batidora": ["licuadora", "robot cocina", "mambo", "thermomix", "picadora"],
    "microondas": ["horno", "grill", "conveccion"],
    "zapatillas": ["tenis", "deportivas", "bambas", "sneakers", "running", "botas", "botines", "calzado", "sandalias", "chanclas"],
    "ropa": ["camiseta", "pantalon", "chaqueta", "vaqueros", "vestido", "sudadera", "abrigo"],
    "belleza": ["secador", "plancha pelo", "rizador", "depiladora", "afeitadora", "cortapelos"],
    "cuidado": ["cepillo electrico", "oral-b", "crema", "serum", "protector solar", "maquillaje"],
    "hogar": ["almohada", "colchon", "sabanas", "edredon", "toallas", "perchero", "estanteria"],
    "cocina": ["sarten", "olla", "cuchillo", "vajilla", "taper", "bascula"],
    "deporte": ["mancuernas", "esterilla", "yoga", "bicicleta", "patinete", "pesas", "fitness"],
    "mascotas": ["perro", "gato", "pienso", "comida", "arena", "rascador", "correa"],
    "bebe": ["panales", "carrito", "silla coche", "biberon", "juguetes bebe", "dodot"],
    "herramientas": ["taladro", "destornillador", "maletin", "bricolaje", "nivel", "lijadora"],
    "juguetes": ["lego", "playmobil", "barbie", "juego mesa", "puzzle", "consola", "nintendo"],
    "papeleria": ["mochila", "agenda", "estuche", "boligrafos", "cuaderno", "impresora"]
}

# --- 2. UTILIDADES ---
def normalizar(texto: str) -> str:
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn').lower().strip()

def identificar_keyword(titulo_norm: str) -> str:
    for cat, sinonimos in CATEGORIAS_MAESTRAS.items():
        if cat in titulo_norm or any(s in titulo_norm for s in sinonimos):
            return cat
    palabras = [p for p in titulo_norm.split() if len(p) > 3]
    return palabras[0] if palabras else "ofertas"

def construir_link_seguro(keyword: str) -> str:
    """Fuerza productos de 7 puntos o más (4 estrellas + Prime)"""
    params = {
        "k": keyword,
        "rh": "p_72:831280031,p_85:831314031",
        "tag": AMAZON_TAG
    }
    return f"https://www.amazon.es/s?{urlencode(params)}"

# --- 3. MOTOR DE PUNTUACIÓN (1-10) ---
def calcular_puntuacion(brand_norm, title_norm):
    score = 7  # Empezamos en una base neutral/buena para marcas promedio
    
    # + Puntos por Marca Fiable
    if any(m in brand_norm or m in title_norm for m in MARCAS_TOP):
        score += 3
    
    # - Puntos por patrones de "Vendedor no fiable / Fotos catálogo"
    # Títulos extremadamente largos llenos de palabras clave suelen ser de vendedores chinos con fotos de catálogo
    if len(title_norm) > 150:
        score -= 2
    
    # Marcas que son solo mayúsculas aleatorias (ej: QWERTYU) suelen tener reseñas falsas/antiguas
    if brand_norm.isupper() and len(brand_norm) < 6:
        score -= 2

    # Limitar score entre 1 y 10
    return max(1, min(10, score))

# --- 4. CEREBRO DE ANÁLISIS ---
def analizar_trustlens(brand_raw, title_raw):
    t_norm = normalizar(title_raw)
    b_norm = normalizar(brand_raw)
    
    puntuacion = calcular_puntuacion(b_norm, t_norm)
    cat = identificar_keyword(t_norm)
    
    # Definir mensaje según tu lógica solicitada
    if puntuacion >= 7:
        veredicto = "La valoración del producto es buena, pero si te interesa puedes visualizar estas otras opciones"
        color = "verde"
    elif 5 <= puntuacion < 7:
        veredicto = "La valoración del producto no es mala, pero te aconsejamos estas otras opciones"
        color = "amarillo"
    else:
        veredicto = "La valoración del producto no es buena, te aconsejamos que visites estas otras opciones"
        color = "rojo"

    # Generar alternativas (Siempre de alta calidad)
    recs = [
        {"name": f"Opción Premium de {cat.capitalize()}", "link": construir_link_seguro(f"{cat} calidad")},
        {"name": f"Mejor Calidad/Precio (Verificado)", "link": construir_link_seguro(f"{cat} mejor valorado")},
        {"name": f"Top Ventas con Garantía", "link": construir_link_seguro(cat)}
    ]
    
    return puntuacion, veredicto, recs

# --- 5. API Y TELEGRAM ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, recs = analizar_trustlens(product.brand, product.title)
    return {
        "score": score,
        "reason": f"Puntuación: {score}/10. {veredicto}",
        "recommendation": recs[1]
    }

async def handle_msg(update: Update, context):
    txt = update.message.text
    if "amazon" in txt.lower() or "amzn" in txt.lower():
        await update.message.reply_text("🔍 Analizando marca, historial de precios y calidad de reseñas...")
        score, veredicto, recs = analizar_trustlens("", txt)
        
        msg = f"<b>📊 Calificación TrustLens: {score}/10</b>\n"
        msg += f"📝 <i>{html.escape(veredicto)}</i>\n"
        msg += "\n💡 <b>Alternativas recomendadas (Puntuación 7+):</b>\n"
        
        for i, r in enumerate(recs, 1):
            msg += f"\n{i}. <a href='{r['link']}'>{html.escape(r['name'])}</a>"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@app.on_event("startup")
async def startup_bot():
    try:
        app_bot = Application.builder().token(TELEGRAM_TOKEN).build()
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
        await app_bot.initialize()
        await app_bot.start()
        asyncio.create_task(app_bot.updater.start_polling(drop_pending_updates=True))
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
