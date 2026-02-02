import asyncio
import unicodedata
from urllib.parse import urlencode
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

# --- UTILIDADES DE TEXTO ---
def normalizar(texto: str) -> str:
    if not texto: return ""
    # Quita tildes, convierte a minúsculas y limpia caracteres especiales
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn').lower().strip()

def extraer_keyword_inteligente(titulo_raw: str) -> str:
    """Extrae las palabras más relevantes del título para que la recomendación sea coherente."""
    t_norm = normalizar(titulo_raw)
    palabras_basura = ["de", "para", "con", "el", "la", "los", "las", "un", "una", "amazon", "oferta", "precio", "talla", "color", "nuevo"]
    palabras = t_norm.split()
    # Filtramos palabras cortas o sin significado
    utiles = [p for p in palabras if p not in palabras_basura and len(p) > 2]
    # Retornamos las 2 o 3 primeras palabras clave (ej: "botines mujer cuero")
    return " ".join(utiles[:3]) if utiles else "productos recomendados"

def construir_busqueda_segura(keyword: str) -> str:
    """Genera el enlace de búsqueda filtrado por 4+ estrellas, Prime y con TU AFILIADO."""
    # Filtros de Amazon: p_72 (4 estrellas o más) y p_85 (Prime)
    query_params = {
        "k": keyword,
        "rh": "p_72:831280031,p_85:831314031",
        "tag": AMAZON_TAG  # <--- TU TAG DE AFILIADO SIEMPRE PRESENTE
    }
    return f"https://www.amazon.es/s?{urlencode(query_params)}"

# --- MARCAS FIABLES ---
MARCAS_TOP = [
    "sony", "samsung", "apple", "xiaomi", "lg", "philips", "bosch", "logitech", "hp", "lenovo", 
    "asus", "dell", "cosori", "cecotec", "roborock", "braun", "oral-b", "remington", "nike", 
    "adidas", "nintendo", "playstation", "xbox", "garmin", "amazfit", "dodot", "lego", "ghd", 
    "rowenta", "tefal", "moulinex", "dyson", "irobot", "anker", "huawei", "msi", "acer", "clarks", "isdin"
]

# --- CATEGORÍAS FIJAS (Sinónimos) ---
CATEGORIAS = {
    "auriculares": ["headphones", "cascos", "airpods", "earbuds"],
    "portatil": ["laptop", "ordenador", "macbook"],
    "movil": ["smartphone", "telefono", "iphone", "galaxy"],
    "freidora": ["air fryer", "cosori", "freidora sin aceite"],
    "reloj": ["smartwatch", "reloj inteligente"],
    "zapatillas": ["sneakers", "zapatos", "botas", "botines", "calzado"]
}

# --- LÓGICA CORE ---
def analizar_inteligente(brand_raw, title_raw):
    title_norm = normalizar(title_raw)
    brand_norm = normalizar(brand_raw)
    
    # 1. Identificar la palabra clave para la búsqueda
    keyword_encontrada = ""
    for cat, sinonimos in CATEGORIAS.items():
        if cat in title_norm or any(s in title_norm for s in sinonimos):
            keyword_encontrada = cat
            break
    
    if not keyword_encontrada:
        keyword_encontrada = extraer_keyword_inteligente(title_raw)

    # 2. Análisis de fiabilidad (Caso A o B)
    es_fiable = any(m in brand_norm or m in title_norm for m in MARCAS_TOP)
    
    if es_fiable:
        veredicto = "✅ Parece fiable"
        razon = "Lo sentimos, aún no hemos evaluado este producto; pero parece fiable. También puede visitar estos productos similares:"
        score = 10
    else:
        veredicto = "⚠️ Precaución"
        razon = "Lo sentimos, aún no hemos evaluado este producto; pero le aconsejamos visitar estos productos similares con mejores garantías:"
        score = 4

    # 3. Generar las 3 Alternativas con AFILIADO
    recs = [
        {"name": f"Opción Premium: {keyword_encontrada.capitalize()}", "link": construir_busqueda_segura(f"{keyword_encontrada} alta gama")},
        {"name": f"Mejor Calidad/Precio (Prime)", "link": construir_busqueda_segura(f"{keyword_encontrada} verificado")},
        {"name": f"Alternativa con Garantía +4⭐", "link": construir_busqueda_segura(keyword_encontrada)}
    ]
    
    return score, veredicto, razon, recs

# --- ENDPOINTS API ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, razon, recs = analizar_inteligente(product.brand, product.title)
    return {
        "score": score,
        "reason": f"{veredicto}: {razon}",
        "recommendation": recs[1]
    }

# --- TELEGRAM ---
async def handle_msg(update: Update, context):
    txt = update.message.text
    if "amazon" in txt.lower() or "amzn" in txt.lower():
        await update.message.reply_text("🕵️ Analizando fiabilidad y buscando alternativas con garantía...")
        score, veredicto, razon, recs = analizar_inteligente("", txt)
        
        msg = f"<b>🔍 Informe TrustLens AI</b>\n\n📊 Veredicto: {html.escape(veredicto)}\n📝 {html.escape(razon)}\n"
        msg += "\n💡 <b>Alternativas con Garantía Prime y Afiliado:</b>\n"
        
        for i, r in enumerate(recs, 1):
            msg += f"\n{i}. <a href='{r['link']}'>{html.escape(r['name'])}</a>"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@app.on_event("startup")
async def startup_bot():
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
        await application.initialize()
        await application.start()
        asyncio.create_task(application.updater.start_polling(drop_pending_updates=True))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
