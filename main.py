"""
TrustLens - Analizador de productos tech en Amazon
Solo valora tecnología y electrodomésticos. Productos no tech muestran mensaje informativo.
"""
import os
import asyncio
import re
import unicodedata
import logging
from urllib.parse import urlencode
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import html

# Cargar .env
_env_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_env_dir, ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key.strip() and val.strip() and key.strip() not in os.environ:
                    os.environ[key.strip()] = val.strip().strip("'\"")
else:
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AMAZON_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "trustlens05-21")
PORT = int(os.getenv("PORT", 8000))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MSG_NO_TECH = "Lo sentimos. Aún no contamos con valoración ni recomendaciones de este producto. En breve iremos ampliando los productos valorados."


class Product(BaseModel):
    title: str = ""
    brand: str = ""
    url: str = ""
    price: str | None = None
    rating: str | None = None
    reviewCount: str | None = None
    hasCoupon: bool = False
    soldBy: str | None = None
    fulfilledBy: str | None = None


# --- PRODUCTOS TECH + ELECTRODOMÉSTICOS + ACCESORIOS ---
TECH_KEYWORDS = [
    # Tecnología
    "tv", "televisor", "television", "televisión","smart tv", "oled", "qled", "4k", "uhd",
    "smartphone", "movil", "móvil", "telefono", "teléfono", "iphone", "galaxy", "celular",
    "tablet", "ipad", "kindle", "ereader",
    "portatil", "laptop", "ordenador", "notebook", "macbook",
    "monitor", "pantalla", "display",
    "auriculares", "cascos", "headphones", "airpods", "earbuds",
    "smartwatch", "reloj inteligente", "pulsera actividad", "fitbit", "garmin", "amazfit",
    "cargador", "power bank", "bateria externa", "cable usb", "usb-c",
    "router", "wifi", "repetidor", "mesh",
    "webcam", "cámara web",
    "teclado", "raton", "mouse", "keyboard",
    "disco duro", "ssd", "hdd", "almacenamiento",
    "impresora", "proyector",
    "fire stick", "chromecast", "tv box", "reproductor streaming",
    "aspiradora robot", "robot aspirador", "roomba", "roborock",
    "drone", "dron",
    "cámara", "camara", "gopro",
    "consola", "playstation", "xbox", "nintendo",
    "altavoz", "speaker", "soundbar", "alexa", "google home",
    # Electrodomésticos
    "electrodoméstico", "electrodomestico",
    "lavadora", "nevera", "congelador", "frigorifico", "frigorífico", "lavavajillas",
    "horno", "microondas", "cafetera", "batidora", "tostadora", "plancha",
    "secadora", "aire acondicionado", "ventilador", "aspiradora",
    "robot cocina", "termomix", "airfryer", "freidora aire",
    # Accesorios (tech/móvil)
    "accesorio", "funda", "soporte", "base de carga", "adaptador",
    "protector pantalla", "mochila portatil", "maletin",
]

MARCAS_VIP = [
    "apple", "samsung", "sony", "lg", "philips", "hp", "lenovo", "asus",
    "dell", "acer", "msi", "logitech", "anker", "jbl", "bose", "sennheiser",
    "xiaomi", "huawei", "oneplus", "google", "amazon", "microsoft",
    "roborock", "dyson", "cecotec", "tp-link", "asus", "netgear",
    "candy", "bosch", "siemens", "electrolux", "whirlpool", "beko", "aeg",
]


def normalizar(texto: str) -> str:
    if not texto:
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if unicodedata.category(c) != "Mn").lower().strip()


def es_tech(titulo: str, brand: str = "") -> bool:
    t = normalizar(f"{titulo} {brand}")
    return any(kw in t for kw in TECH_KEYWORDS) or any(m in t for m in MARCAS_VIP)


def es_url_amazon(texto: str) -> bool:
    return bool(re.search(r"amazon\.(es|com|de|fr|it)|amzn\.", (texto or "").lower()))


def detectar_merchant_tipo(sold_by: str, fulfilled_by: str) -> str:
    """Devuelve: 'amazon' | 'third_fulfilled' | 'third_only'"""
    s = (sold_by or "").lower()
    f = (fulfilled_by or "").lower()
    if "amazon" in s and ("amazon" in f or not f):
        return "amazon"
    if "amazon" in f or "prime" in f:
        return "third_fulfilled"
    return "third_only"


def _safe_float(v: str | None) -> float:
    if not v:
        return 0.0
    m = re.search(r"[\d,]+[.,]?\d*", str(v).replace(",", "."))
    return float(m.group(0).replace(",", ".")) if m else 0.0


def _safe_int(v: str | None) -> int:
    if not v:
        return 0
    return int(re.sub(r"\D", "", str(v)[:50]) or 0)


def extraer_especificaciones(titulo: str) -> str:
    """Extrae specs para alternativas coherentes: 55", 32 pulgadas, etc."""
    t = titulo
    specs = []
    for pat in [r"(\d+)\s*['\"]", r"(\d+)\s*pulgada", r"(\d+)\s*inch", r"(\d+)\s*gb", r"(\d+)\s*tb", r"(\d+)\s*kg"]:
        m = re.search(pat, t, re.I)
        if m:
            specs.append(m.group(0).strip())
    return " ".join(specs[:2]) if specs else ""


def detectar_termino_busqueda(titulo: str) -> str:
    """Término base para alternativas. Prioriza tipo de producto sobre marca (ej. Candy lavadora -> lavadora)."""
    if not titulo or len(titulo) < 3:
        return "producto tech"
    t = normalizar(titulo)
    # Orden: electrodomésticos primero (evita Candy->caramelos), luego tech
    mapping = [
        ("lavadora", ["lavadora", "washer"]),
        ("secadora", ["secadora", "secaropa"]),
        ("nevera", ["nevera", "frigorifico", "frigorífico", "refrigerador"]),
        ("congelador", ["congelador", "freezer"]),
        ("lavavajillas", ["lavavajillas", "lavavajilla"]),
        ("horno", ["horno", "hornos"]),
        ("microondas", ["microondas"]),
        ("cafetera", ["cafetera", "cafeteras"]),
        ("aspiradora", ["aspiradora", "aspirador"]),
        ("robot aspirador", ["robot aspirador", "roomba", "roborock"]),
        ("tv 55", ["tv 55", "55 pulgadas", "55 inch", "televisor 55"]),
        ("tv 65", ["tv 65", "65 pulgadas", "65 inch"]),
        ("tv 50", ["tv 50", "50 pulgadas"]),
        ("tv 43", ["tv 43", "43 pulgadas"]),
        ("tv 32", ["tv 32", "32 pulgadas"]),
        ("smartphone", ["smartphone", "movil", "telefono", "iphone", "galaxy"]),
        ("tablet", ["tablet", "ipad"]),
        ("smartwatch", ["smartwatch", "reloj inteligente"]),
        ("auriculares bluetooth", ["auriculares bluetooth", "cascos bluetooth"]),
        ("auriculares", ["auriculares", "cascos", "headphones"]),
        ("portatil", ["portatil", "laptop", "ordenador"]),
        ("monitor", ["monitor", "pantalla"]),
        ("cargador movil", ["cargador", "cargador movil"]),
        ("power bank", ["power bank", "bateria externa"]),
        ("fire stick", ["fire stick", "fire tv"]),
        ("chromecast", ["chromecast"]),
    ]
    specs = extraer_especificaciones(titulo)
    for term, kws in mapping:
        if any(kw in t for kw in kws):
            return f"{term} {specs}".strip()
    # Fallback: primera palabra relevante (evitar marcas que coinciden con palabras comunes)
    excluir = ("the", "and", "para", "con", "pro", "max", "plus", "candy", "new")
    palabras = t.split()
    for p in palabras:
        if len(p) > 2 and p not in excluir:
            return f"{p} {specs}".strip()
    return ("producto" + " " + specs).strip()


# Parámetros Amazon.es: 4+ estrellas, Prime
# p_72:831280031 = 4+ estrellas en Amazon.es
# p_85:20930978031 = Prime en Amazon.es
RH_4_ESTRELLAS = "p_72:831280031"
RH_PRIME = "p_85:20930978031"

# Rangos de precio para preguntar al usuario (low_cents, high_cents)
RANGOS_PRECIO = {
    "a": (0, 2999),       # 0 - 29,99 €
    "b": (3000, 4999),    # 30 - 49,99 €
    "c": (5000, 9999),    # 50 - 99,99 €
    "d": (10000, None),   # más de 100 €
}


def teclado_rango_precio() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("a) 0 - 29,99 €", callback_data="price_a")],
        [InlineKeyboardButton("b) 30 - 49,99 €", callback_data="price_b")],
        [InlineKeyboardButton("c) 50 - 99,99 €", callback_data="price_c")],
        [InlineKeyboardButton("d) Más de 100 €", callback_data="price_d")],
    ]
    return InlineKeyboardMarkup(kb)


def _enviar_links_busqueda(bot, chat_id: int, termino: str, low_p: int | None, high_p: int | None):
    """Envía los 3 enlaces de búsqueda con el rango de precio indicado."""
    filtro_calidad = [RH_4_ESTRELLAS]
    def mk_link(sort, rh=None):
        return construir_link(termino, sort=sort, rh_filters=rh or filtro_calidad, low_price=low_p, high_price=high_p)
    links = [
        (f"{termino} – Mejor valorados", mk_link("review-rank")),
        (f"{termino} – Más vendidos", mk_link("popularity-rank")),
        (f"{termino} – Prime", mk_link("review-rank", [RH_4_ESTRELLAS, RH_PRIME])),
    ]
    link_esc = lambda u: u.replace("&", "&amp;")
    partes = [f"🔍 <b>Top productos para: {html.escape(termino)}</b>"]
    if low_p is not None or high_p is not None:
        rango = []
        if low_p is not None:
            rango.append(f"desde {low_p//100}€")
        if high_p is not None:
            rango.append(f"hasta {high_p//100}€")
        partes[0] += f" ({', '.join(rango)})"
    partes[0] += "\n"
    for i, (nombre, url) in enumerate(links, 1):
        partes.append(f'{i}. <a href="{link_esc(url)}">{html.escape(nombre)}</a>')
    return bot.send_message(
        chat_id=chat_id,
        text="\n".join(partes),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


def extraer_rango_precio(texto: str) -> tuple[int | None, int | None]:
    """Extrae rango de precio del texto. Devuelve (low_cents, high_cents) o (None, None).
    Ej: 'menos de 50' -> (None, 5000), '50-100' -> (5000, 10000), 'más de 200' -> (20000, None)
    """
    t = (texto or "").lower().strip()
    low, high = None, None
    # Buscar números con € o euros
    numeros = re.findall(r"(\d+)\s*(?:€|euros?|eur)?", t, re.I)
    if not numeros:
        return (None, None)
    vals = [int(n) for n in numeros[:2]]
    if "menos de" in t or "hasta" in t or "máximo" in t:
        high = (vals[0] if vals else 0) * 100
        return (None, high)
    if "más de" in t or "desde" in t or "mínimo" in t:
        low = (vals[0] if vals else 0) * 100
        return (low, None)
    if len(vals) >= 2:
        return (vals[0] * 100, vals[1] * 100)
    if len(vals) == 1:
        return (vals[0] * 100, None)
    return (None, None)


def construir_link(
    keyword: str,
    sort: str | None = None,
    rh_filters: list[str] | None = None,
    low_price: int | None = None,
    high_price: int | None = None,
) -> str:
    """Construye URL de búsqueda Amazon.es con filtros.
    Precios en céntimos (50€ = 5000).
    """
    params = {"k": keyword.strip(), "tag": AMAZON_TAG}
    if sort:
        params["s"] = sort
    if rh_filters:
        params["rh"] = ",".join(rh_filters)
    if low_price:
        params["low-price"] = str(low_price)
    if high_price:
        params["high-price"] = str(high_price)
    return f"https://www.amazon.es/s?{urlencode(params)}"


def anadir_tag(url: str) -> str:
    if not url:
        return ""
    url = re.sub(r"[?&]tag=[^&]*", "", url)
    return f"{url}{'&' if '?' in url else '?'}tag={AMAZON_TAG}"


def analizar_tech(brand: str, title: str, rating: str, review_count: str,
                  sold_by: str, fulfilled_by: str, product_url: str) -> dict:
    merchant = detectar_merchant_tipo(sold_by, fulfilled_by)
    rating_val = _safe_float(rating)
    reviews = _safe_int(review_count)
    detalles = []
    score = 10

    # 1. Sold by / Fulfilled by (jerarquía principal)
    if merchant == "amazon":
        detalles.append("Vendido y enviado por Amazon: máxima confianza.")
    elif merchant == "third_fulfilled":
        score -= 2
        detalles.append("Vendido por tercero, enviado por Amazon (Prime). Revisa el perfil del vendedor.")
    else:
        score -= 4
        detalles.append("Vendido y enviado por tercero. Verifica el perfil del vendedor antes de comprar.")

    # 2. Marca
    if any(m in normalizar(brand or "") or m in normalizar(title) for m in MARCAS_VIP):
        detalles.append("Marca reconocida.")
    else:
        score -= 1
        detalles.append("Marca no verificada en nuestra lista.")

    # 3. Reseñas
    if reviews > 0:
        if rating_val >= 4.5 and reviews > 100:
            detalles.append("Buena valoración y volumen de reseñas.")
        elif rating_val < 4.0:
            score -= 2
            detalles.append("Valoración baja. Revisa las reseñas de 1-2 estrellas.")
        if reviews < 10:
            score -= 1
            detalles.append("Pocas reseñas. Ten precaución.")
    else:
        score -= 2
        detalles.append("Sin reseñas. Desaconsejado.")

    # 4. Título spam
    if len(title) > 160:
        score -= 1
        detalles.append("Título excesivamente largo (posible SEO spam).")

    score = max(0, min(10, score))
    termino = detectar_termino_busqueda(title)

    # Semáforo y textos
    if score >= 8:
        color, emoji = "#2ecc71", "🟢"
        titulo_msg = "Muy buen producto"
        btn_text = "Comprar"
        alt_text = "También te podría interesar:"
    elif score >= 5:
        color, emoji = "#f1c40f", "🟡"
        titulo_msg = "Producto mejorable"
        btn_text = "Comprar"
        alt_text = "Te podría interesar consultar estas opciones:"
    else:
        color, emoji = "#e74c3c", "🔴"
        titulo_msg = "Producto con valoración baja"
        btn_text = "Comprar igualmente"
        alt_text = "Te recomiendo consultar estas otras opciones:"

    filtro_calidad = [RH_4_ESTRELLAS]  # 4+ estrellas (proxy de productos con buena valoración)
    recs = [
        {"name": f"{termino} – Mejor valorados", "link": construir_link(termino, sort="review-rank", rh_filters=filtro_calidad)},
        {"name": f"{termino} – Más vendidos", "link": construir_link(termino, sort="popularity-rank", rh_filters=filtro_calidad)},
        {"name": f"{termino} – Prime", "link": construir_link(termino, sort="review-rank", rh_filters=[RH_4_ESTRELLAS, RH_PRIME])},
    ]
    for r in recs:
        r["affiliate_link"] = r["link"]

    buy_link = anadir_tag(product_url) if product_url and "amazon." in product_url.lower() else None

    return {
        "isTech": True,
        "score": score,
        "emoji": emoji,
        "color": color,
        "tituloMsg": titulo_msg,
        "reason": " ".join(detalles),
        "details": detalles,
        "btnText": btn_text,
        "buyLink": buy_link,
        "altText": alt_text,
        "recommendations": recs,
        "hasCoupon": False,
    }


@app.post("/analyze")
async def analyze(product: Product):
    if not es_tech(product.title or "", product.brand or ""):
        return {
            "isTech": False,
            "message": MSG_NO_TECH,
        }

    r = analizar_tech(
        product.brand or "",
        product.title or "",
        product.rating or "",
        product.reviewCount or "",
        product.soldBy or "",
        product.fulfilledBy or "",
        product.url or "",
    )
    r["hasCoupon"] = product.hasCoupon
    return r


@app.get("/search")
async def search_top3(q: str):
    """Búsqueda directa: devuelve enlaces a productos (solo tech)."""
    termino = q.strip() or "producto"
    if not es_tech(termino, ""):
        return {"isTech": False, "message": MSG_NO_TECH}
    filtro = [RH_4_ESTRELLAS]
    links = {
        "mejor_valorados": construir_link(termino, sort="review-rank", rh_filters=filtro),
        "mas_vendidos": construir_link(termino, sort="popularity-rank", rh_filters=filtro),
        "prime": construir_link(termino, sort="review-rank", rh_filters=[RH_4_ESTRELLAS, RH_PRIME]),
    }
    return {"isTech": True, "links": links, "searchTerm": termino}


@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok", "service": "TrustLens"}


# --- BOT TELEGRAM ---
START_MSG = """🔍 *TrustLens* – Analizador de productos tech en Amazon

*Tienes 2 opciones:*

1️⃣ *Pega un enlace* de un producto de Amazon  
   → Te daré valoración (0-10), precio, motivos y 3 alternativas

2️⃣ *Escribe el tipo de producto* (ej: TV 55, auriculares, lavadora)  
   → Te pediré elegir rango de precio (0-30€, 30-50€, 50-100€, +100€)  
   → O escribe el rango en el mensaje: "auriculares menos de 50€"

Solo analizamos *tecnología y electrodomésticos*."""


async def cmd_start(update: Update, context):
    await update.message.reply_text(START_MSG, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    context.user_data.pop("awaiting_price", None)
    context.user_data.pop("termino", None)


async def handle_price_callback(update: Update, context):
    """Procesa la elección de rango de precio del usuario."""
    q = update.callback_query
    await q.answer()
    if not q.data or not q.data.startswith("price_"):
        return
    opt = q.data.replace("price_", "")
    if opt not in RANGOS_PRECIO:
        return
    termino = context.user_data.pop("termino", None)
    context.user_data.pop("awaiting_price", None)
    if not termino:
        await q.edit_message_text("La sesión ha expirado. Vuelve a buscar el producto.")
        return
    low_p, high_p = RANGOS_PRECIO[opt]
    await _enviar_links_busqueda(context.bot, q.message.chat_id, termino, low_p, high_p)


async def handle_msg(update: Update, context):
    txt = (update.message.text or "").strip()
    if not txt:
        return

    product_url = txt if es_url_amazon(txt) else ""
    title, brand, sold_by, fulfilled_by, has_coupon = "", "", "", "", False
    rating, review_count, price = "", "", ""

    if es_url_amazon(txt):
        await update.message.reply_text("🕵️ Analizando...")
        try:
            from scraper import extraer_datos_producto
            d = extraer_datos_producto(txt)
            if d:
                title = d.get("title", txt)
                brand = d.get("brand", "")
                sold_by = d.get("soldBy", "")
                fulfilled_by = d.get("fulfilledBy", "")
                has_coupon = d.get("hasCoupon", False)
                product_url = d.get("url", txt)
                rating = d.get("rating", "")
                review_count = d.get("reviewCount", "")
                price = d.get("price", "") or ""
        except Exception as e:
            logger.warning("Scraper: %s", e)
    else:
        # Modo búsqueda: 3 enlaces (mejor valorados, más vendidos, prime)
        if not es_tech(txt, ""):
            await update.message.reply_text(MSG_NO_TECH)
            return
        termino = detectar_termino_busqueda(txt)
        low_p, high_p = extraer_rango_precio(txt)
        # Si no especificó precio, preguntar con teclado
        if low_p is None and high_p is None:
            context.user_data["termino"] = termino
            context.user_data["awaiting_price"] = True
            await update.message.reply_text(
                f"💰 <b>Elige un rango de precio para: {html.escape(termino)}</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=teclado_rango_precio(),
            )
            return
        # Tiene rango de precio: devolver enlaces directamente
        await _enviar_links_busqueda(context.bot, update.effective_chat.id, termino, low_p, high_p)
        return

    if not title:
        title = txt

    if not es_tech(title, brand):
        await update.message.reply_text(MSG_NO_TECH)
        return

    r = analizar_tech(brand, title, rating, review_count, sold_by, fulfilled_by, product_url)
    r["hasCoupon"] = has_coupon

    def esc_url(u):
        return (u or "").replace("&", "&amp;")

    cupon_badge = " 🏷️ Cupón disponible" if has_coupon else ""
    msg = f"{r['emoji']} <b>TrustLens: {r['score']}/10</b>{cupon_badge}\n\n"
    if price:
        msg += f"💰 <b>Precio:</b> {html.escape(price)}\n\n"
    msg += f"<b>{r['tituloMsg']}</b>\n\n"
    for d in r["details"]:
        msg += f"• {html.escape(str(d))}\n"
    if has_coupon:
        msg += "\n⚠️ <b>¡Cupón de descuento!</b> No olvides marcarlo antes de comprar.\n"
    msg += f"\n{html.escape(r['altText'])}\n"
    if r.get("buyLink"):
        msg += f"\n🛒 <a href=\"{esc_url(r['buyLink'])}\">{html.escape(r['btnText'])}</a>\n"
    for i, rec in enumerate(r["recommendations"], 1):
        msg += f"{i}. <a href=\"{esc_url(rec['link'])}\">{html.escape(rec['name'])}</a>\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@app.on_event("startup")
async def startup_bot():
    if not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN no configurado.")
        return
    try:
        bot = Application.builder().token(TELEGRAM_TOKEN).build()
        bot.add_handler(CommandHandler("start", cmd_start))
        bot.add_handler(CallbackQueryHandler(handle_price_callback, pattern="^price_[abcd]$"))
        bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
        await bot.initialize()
        await bot.start()
        asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
        logger.info("Bot Telegram iniciado.")
    except Exception as e:
        logger.error("Bot: %s", e)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
