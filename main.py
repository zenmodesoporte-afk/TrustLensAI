import os
import asyncio

# Cargar .env lo antes posible (varias rutas por compatibilidad)
_env_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_env_dir, ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and val and key not in os.environ:
                    os.environ[key] = val
else:
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
        load_dotenv()
    except ImportError:
        pass

import unicodedata
import logging
from urllib.parse import urlencode
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import html
import re

# --- CONFIGURACIÓN (variables de entorno) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AMAZON_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "trustlens05-21")
PORT = int(os.getenv("PORT", 8000))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Product(BaseModel):
    title: str = ""
    brand: str = ""
    url: str = ""
    price: str | None = None
    rating: str | None = None
    reviewCount: str | None = None
    hasCoupon: bool = False


# --- 1. LISTA DE MARCAS TOP ---
MARCAS_VIP = [
    "apple", "samsung", "sony", "xiaomi", "lg", "philips", "hp", "lenovo", "asus", "logitech",
    "cosori", "cecotec", "roborock", "dyson", "nintendo", "nike", "adidas", "puma", "clarks",
    "bosch", "makita", "oral-b", "braun", "rowenta", "moulinex", "tefal", "isdin", "garmin",
    "amazfit", "anker", "tp-link", "lego", "dodot", "ghd", "remington", "canon", "nikon",
]

# --- 2. CATEGORÍAS Y TEMÁTICAS ---
# (tipo, término_búsqueda, [palabras detección])
CATEGORIAS_MAESTRAS = [
    # Libros
    ("libro", "libros", ["libro", "libros", "novela", "ensayo", "ebook", "tapa blanda", "tapa dura"]),
    # Música
    ("musica", "cd musica", ["cd", "cds", "disco", "discos", "vinilo", "vinilos", "lp", "vinil"]),
    # Calzado (orden: específico primero)
    ("calzado", "botas mujer", ["botas mujer", "bota mujer"]),
    ("calzado", "botas hombre", ["botas hombre", "bota hombre"]),
    ("calzado", "botas", ["botas", "botines", "bota"]),
    ("calzado", "zapatillas running", ["zapatillas running", "running mujer", "running hombre"]),
    ("calzado", "zapatillas deportivas", ["zapatillas", "tenis", "deportivas", "bambas", "sneakers"]),
    ("calzado", "sandalias mujer", ["sandalias mujer", "sandalias"]),
    ("calzado", "zapato mujer", ["zapato mujer", "tacon", "tacón", "tacones"]),
    ("calzado", "zapato hombre", ["zapato hombre", "mocasin", "mocasín"]),
    # Tech
    ("tech", "auriculares bluetooth", ["auriculares bluetooth", "cascos bluetooth", "inalambricos"]),
    ("tech", "auriculares", ["cascos", "airpods", "earbuds", "headphones", "diadema", "auriculares"]),
    ("tech", "cargador movil", ["cargador", "cargadores", "cargador movil", "cargador telefono"]),
    ("tech", "power bank", ["power bank", "bateria externa", "batería externa"]),
    ("tech", "cable usb", ["cable usb", "cable usb-c", "cable carga"]),
    ("tech", "portatil", ["laptop", "ordenador", "macbook", "notebook", "sobremesa", "portatil"]),
    ("tech", "smartphone", ["smartphone", "telefono", "iphone", "galaxy", "celular"]),
    ("tech", "smartwatch", ["smartwatch", "reloj inteligente", "pulsera actividad", "fitbit", "garmin"]),
    ("tech", "tablet", ["ipad", "galaxy tab", "tableta", "kindle"]),
    ("tech", "monitor", ["monitor", "pantalla", "display"]),
    ("tech", "teclado", ["teclado", "keyboard"]),
    ("tech", "raton", ["raton", "ratón", "mouse"]),
    # Hogar
    ("hogar", "freidora aire", ["air fryer", "freidora aire", "freidora sin aceite"]),
    ("hogar", "robot aspirador", ["robot aspirador", "roomba", "roborock", "conga"]),
    ("hogar", "aspiradora", ["aspiradora", "escoba electrica"]),
    ("hogar", "batidora", ["batidora", "batidora vaso", "licuadora"]),
    ("hogar", "cafetera", ["cafetera", "nespresso", "espresso"]),
    ("hogar", "secador pelo", ["secador", "secador pelo"]),
    ("hogar", "plancha pelo", ["plancha pelo", "rizador", "tenazas"]),
    ("hogar", "depiladora", ["depiladora", "afeitadora electrica"]),
    ("hogar", "reproductor streaming", ["fire stick", "chromecast", "tv box"]),
    # Complementos
    ("complemento", "mochila", ["mochila", "mochilas"]),
    ("complemento", "bolso", ["bolso", "bolsos", "bolso mujer"]),
    ("complemento", "reloj", ["reloj hombre", "reloj mujer", "reloj pulsera"]),
]

# Temáticas de libros → término de búsqueda
TEMAS_LIBROS = [
    ("thriller", ["thriller", "suspense", "policiaco", "policíaco", "misterio", "crimen"]),
    ("novela negra", ["negra", "noir", "detective"]),
    ("romance", ["romance", "romantica", "amor", "bodas"]),
    ("fantasia", ["fantasia", "fantasía", "ficcion", "ficción", "epica", "épica"]),
    ("ciencia ficcion", ["ciencia ficcion", "scifi", "distopia", "distopía"]),
    ("autoayuda", ["autoayuda", "desarrollo personal", "motivacion", "productividad"]),
    ("cocina", ["cocina", "recetas", "gastronomia", "chef"]),
    ("historia", ["historia", "historico", "histórico", "guerra", "imperio"]),
    ("biografia", ["biografia", "biografía", "memorias", "autobiografia"]),
    ("negocios", ["negocios", "empresa", "liderazgo", "emprendimiento", "economia"]),
]

# Géneros de música → término de búsqueda
GENEROS_MUSICA = [
    ("rock", ["rock", "metal", "punk", "indie"]),
    ("pop", ["pop", "latino", "latina"]),
    ("electronica", ["electronica", "electrónica", "dance", "house", "techno"]),
    ("clasica", ["clasica", "clásica", "orquesta", "sinfonia"]),
    ("jazz", ["jazz", "blues"]),
    ("flamenco", ["flamenco", "española", "espanola"]),
]

# Palabras a ignorar cuando el mensaje es una URL
URL_BASURA = {"https", "http", "www", "amazon", "amzn", "amazon", "amazon", "es", "com", "dp", "gp", "ref", "html"}


def normalizar(texto: str) -> str:
    if not texto:
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if unicodedata.category(c) != "Mn").lower().strip()


def es_url_amazon(texto: str) -> bool:
    return bool(re.search(r"amazon\.(es|com|de|fr|it)|amzn\.", texto.lower()))


def detectar_categoria(titulo_raw: str) -> "tuple[str, str]":
    """
    Detecta tipo y término de búsqueda.
    Retorna (tipo, termino) ej: ("libro", "libros thriller"), ("musica", "cd rock")
    """
    t_norm = normalizar(titulo_raw)
    palabras_titulo = set(re.findall(r"\b\w{4,}\b", t_norm))

    # Si parece URL
    if es_url_amazon(titulo_raw):
        utiles = [p for p in palabras_titulo if p not in URL_BASURA and not p.startswith("b0")]
        return ("producto", utiles[0] if utiles else "producto")

    # 1. Buscar en categorías (orden importa)
    for tipo, termino, keywords in CATEGORIAS_MAESTRAS:
        for kw in keywords:
            if kw in t_norm:
                if termino == "smartphone" and "botas" in t_norm:
                    continue
                return (tipo, termino)

    # 2. Prohibidas
    prohibidas = {"complemento", "suplemento", "vitamina", "mineral", "dieta", "omega", "capsula", "pastilla", "oferta"}
    if palabras_titulo & prohibidas:
        utiles = [p for p in palabras_titulo if p not in prohibidas]
        return ("producto", utiles[0] if utiles else "producto")

    # 3. Fallback (no incluir mujer/hombre: son atributos útiles)
    basura = {
        "con", "para", "del", "desde", "mejor", "oferta", "precio", "barato", "nuevo", "color",
        "talla", "pulgadas", "pulgada", "cm", "mm", "unidades", "pack", "juego", "inalambrico",
        "bluetooth", "wifi", "hd", "4k", "compatible", "led", "lcd", "pro", "plus",
    } | set(MARCAS_VIP)
    utiles = [p for p in palabras_titulo if p not in basura]
    return ("producto", utiles[0] if utiles else "producto")


def detectar_tema_libro(titulo_raw: str) -> str | None:
    """Detecta temática de un libro para sugerencias."""
    t_norm = normalizar(titulo_raw)
    for tema, keywords in TEMAS_LIBROS:
        for kw in keywords:
            if kw in t_norm:
                return tema
    return None


def detectar_genero_musica(titulo_raw: str) -> str | None:
    """Detecta género musical para sugerencias."""
    t_norm = normalizar(titulo_raw)
    for genero, keywords in GENEROS_MUSICA:
        for kw in keywords:
            if kw in t_norm:
                return genero
    return None


def extraer_atributos(titulo_raw: str) -> list[str]:
    """Extrae atributos relevantes para afinar búsquedas (mujer, hombre, invierno, etc.)."""
    t_norm = normalizar(titulo_raw)
    atributos = []
    mods = [
        ("mujer", ["mujer", "female", "dama"]),
        ("hombre", ["hombre", "male", "caballero", "man"]),
        ("nino", ["nino", "niño", "infantil", "kids", "nina", "niña"]),
        ("invierno", ["invierno", "invernal", "abrigo"]),
        ("verano", ["verano", "estival"]),
        ("deportivo", ["deportivo", "sport", "gym", "running", "fitness"]),
        ("formal", ["formal", "oficina", "elegante"]),
    ]
    for attr, kws in mods:
        if any(kw in t_norm for kw in kws):
            atributos.append(attr)
    return atributos


def construir_link(keyword: str, extra: str = "") -> str:
    """Enlace de búsqueda con tag de afiliados."""
    search_term = f"{keyword} {extra}".strip()
    params = {
        "k": search_term,
        "rh": "p_72:831280031,p_85:831314031",
        "tag": AMAZON_TAG,
    }
    return f"https://www.amazon.es/s?{urlencode(params)}"


def anadir_tag_afiliado(url: str) -> str:
    """Añade o reemplaza el tag de afiliados en una URL de Amazon."""
    if not url:
        return ""
    url = re.sub(r"[?&]tag=[^&]*", "", url)
    sep = "&" if "?" in url else "?"
    return f"{url.rstrip('&')}{sep}tag={AMAZON_TAG}"


# --- 4. MOTOR DE ANÁLISIS ---
def analizar_producto(brand_raw: str, title_raw: str, product_url: str = ""):
    title = normalizar(title_raw)
    brand = normalizar(brand_raw)

    score = 10
    detalles = []

    # Análisis de fiabilidad
    if any(m in brand or m in title for m in MARCAS_VIP):
        detalles.append("🟢 Marca fiable y verificada.")
    else:
        score -= 2
        detalles.append("🟡 Marca no verificada (Vendedor externo).")

    if len(title_raw) > 160:
        score -= 2
        detalles.append("🔴 Título excesivo (Patrón de fotos de catálogo).")

    if brand and len(brand) < 6 and brand.isupper():
        score -= 3
        detalles.append("🔴 Nombre de marca sospechoso (Letras aleatorias).")

    score = max(1, score)
    tipo, esencia = detectar_categoria(title_raw)

    if score >= 7:
        veredicto = "La valoración del producto es buena, pero si te interesa puedes visualizar estas otras opciones"
        color = "#2ecc71"
        emoji = "🟢"
    elif 5 <= score < 7:
        veredicto = "La valoración del producto no es mala, pero te aconsejamos estas otras opciones"
        color = "#f1c40f"
        emoji = "🟡"
    else:
        veredicto = "La valoración del producto no es buena, te aconsejamos que visites estas otras opciones"
        color = "#e74c3c"
        emoji = "🔴"

    # Recomendaciones según tipo de producto
    atributos = extraer_atributos(title_raw)
    sufijo = " " + " ".join(atributos[:2]).strip() if atributos else ""

    if tipo == "libro":
        tema = detectar_tema_libro(title_raw)
        base = f"libros {tema}" if tema else "libros"
        recs = [
            {"name": f"Libros de {tema}" if tema else "Libros recomendados", "link": construir_link(base)},
            {"name": "Libros más vendidos", "link": construir_link("libros mas vendidos")},
            {"name": "Bestsellers", "link": construir_link("libros bestseller")},
        ]
    elif tipo == "musica":
        genero = detectar_genero_musica(title_raw)
        base = f"cd {genero}" if genero else "cd musica"
        recs = [
            {"name": f"CDs {genero}" if genero else "CDs música", "link": construir_link(base)},
            {"name": "CDs más vendidos", "link": construir_link("cd musica mas vendidos")},
            {"name": "Vinilos", "link": construir_link(f"vinilos {genero}" if genero else "vinilos")},
        ]
    else:
        termino_base = f"{esencia}{sufijo}".strip()
        recs = [
            {"name": f"{esencia.capitalize()}{sufijo} – Mejor valorados", "link": construir_link(termino_base)},
            {"name": f"{esencia.capitalize()}{sufijo} – Más vendidos", "link": construir_link(termino_base, "mas vendido")},
            {"name": f"{esencia.capitalize()}{sufijo} – Prime", "link": construir_link(termino_base, "prime")},
        ]

    # Enlace "Comprar" con afiliados para productos con buena valoración (8-10)
    buy_link = None
    if score >= 8 and product_url and "amazon." in product_url.lower():
        buy_link = anadir_tag_afiliado(product_url)

    return score, veredicto, detalles, recs, color, emoji, buy_link


# --- 5. API ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, detalles, recs, color, emoji, buy_link = analizar_producto(
        product.brand, product.title, product.url or ""
    )
    for r in recs:
        r["affiliate_link"] = r["link"]
    return {
        "score": score,
        "reason": veredicto,
        "details": detalles,
        "recommendation": recs[0],
        "recommendations": recs,
        "color": color,
        "emoji": emoji,
        "veredicto": "excelente" if score >= 7 else ("mediocre" if score >= 5 else "mala"),
        "buy_link": buy_link,
        "hasCoupon": product.hasCoupon,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "TrustLens"}


# --- 6. BOT TELEGRAM ---
async def cmd_start(update: Update, context):
    await update.message.reply_text(
        "🔍 *TrustLens* – Analizador de productos Amazon\n\n"
        "Pega un enlace de Amazon o el título de un producto y te diré si es fiable.\n\n"
        "Si envías un enlace, copia también el título si el análisis no es correcto.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def handle_msg(update: Update, context):
    txt = (update.message.text or "").strip()
    if not txt:
        return

    # Responde a enlaces de Amazon o mensajes que parezcan títulos
    if not (es_url_amazon(txt) or len(txt) > 20):
        return

    await update.message.reply_text("🕵️ Analizando y buscando alternativas...")

    brand = ""
    title = txt
    product_url = txt if es_url_amazon(txt) else ""
    has_coupon = False
    if es_url_amazon(txt):
        try:
            from scraper import extraer_datos_producto
            datos = extraer_datos_producto(txt)
            if datos:
                if datos.get("title"):
                    title = datos["title"]
                if datos.get("brand"):
                    brand = datos["brand"]
                product_url = datos.get("url", txt)
                has_coupon = datos.get("hasCoupon", False)
        except Exception as e:
            logger.warning("Scraper falló: %s. Usando mensaje como título.", e)

    score, veredicto, detalles, recs, color, emoji, buy_link = analizar_producto(brand, title, product_url)

    msg = f"{emoji} <b>Análisis TrustLens: {score}/10</b>\n\n"
    msg += "<b>Desglose:</b>\n"
    for d in detalles:
        msg += f"- {d}\n"
    if has_coupon:
        msg += "\n⚠️ <b>¡Ojo!</b> Este producto tiene un cupón disponible, ¡no olvides marcarlo!\n"
    msg += f"\n📝 <i>{html.escape(veredicto)}</i>\n"
    if buy_link:
        msg += f"\n🛒 <a href='{buy_link}'>Comprar este producto</a>\n"
    for i, r in enumerate(recs, 1):
        msg += f"\n{i}. <a href='{r['link']}'>{html.escape(r['name'])}</a>"

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@app.on_event("startup")
async def startup_bot():
    if not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN no configurado. Bot desactivado.")
        return
    try:
        bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
        bot_app.add_handler(CommandHandler("start", cmd_start))
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
        await bot_app.initialize()
        await bot_app.start()
        asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
        logger.info("Bot Telegram iniciado.")
    except Exception as e:
        logger.error("Error iniciando bot Telegram: %s", e)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)

