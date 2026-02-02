import asyncio
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

# --- LISTA DE MARCAS VIP (La "Lista Blanca") ---
MARCAS_VIP = [
    "sony", "samsung", "apple", "xiaomi", "lg", "philips", "bosch", 
    "logitech", "hp", "lenovo", "asus", "dell", "cosori", "cecotec", 
    "roborock", "braun", "oral-b", "remington", "nike", "adidas", 
    "canon", "nikon", "nintendo", "playstation", "xbox", "garmin", 
    "amazfit", "dodot", "pampers", "lego", "barbie", "playmobil",
    "fischer", "black+decker", "makita", "bosch professional",
    "royal canin", "purina", "isdin", "la roche-posay", "garnier",
    "l'oreal", "maybelline", "ghd", "rowenta", "tefal", "moulinex",
    "dewalt", "stanley", "kärcher", "dyson", "irobot", "tous", "pandora"
]

# --- BASE DE DATOS DE RECOMENDACIONES MULTI-OPCIÓN ---
# Formato: "palabra_clave": [ {Opción 1}, {Opción 2}, {Opción 3} ]
PRODUCTOS_TOP = {
    # --- TECNOLOGÍA: MÓVILES Y TABLETS ---
    "iphone": [
        {"name": "iPhone 13 (Calidad/Precio)", "link": "https://www.amazon.es/dp/B09G9DMQ7Z"},
        {"name": "iPhone 15 (Último Modelo)", "link": "https://www.amazon.es/dp/B0CHXdmF9K"}
    ],
    "samsung galaxy": [
        {"name": "Samsung Galaxy A54 (Top Ventas)", "link": "https://www.amazon.es/dp/B0BYR85X67"},
        {"name": "Samsung S23 Ultra (Premium)", "link": "https://www.amazon.es/dp/B0BTZ595F5"}
    ],
    "xiaomi": [
        {"name": "Xiaomi Redmi Note 13 (Económico)", "link": "https://www.amazon.es/dp/B0CQM3F5D9"},
        {"name": "POCO X6 Pro (Potencia)", "link": "https://www.amazon.es/dp/B0CRVTFV1X"}
    ],
    "movil": [
        {"name": "Samsung Galaxy A54 (Android Recomendado)", "link": "https://www.amazon.es/dp/B0BYR85X67"},
        {"name": "Google Pixel 7a (Mejor Cámara)", "link": "https://www.amazon.es/dp/B0BZJE5L39"},
        {"name": "Xiaomi Redmi 13C (Barato)", "link": "https://www.amazon.es/dp/B0CMZFV6GY"}
    ],
    "smartphone": [
         {"name": "Samsung Galaxy A54", "link": "https://www.amazon.es/dp/B0BYR85X67"},
         {"name": "Google Pixel 7a", "link": "https://www.amazon.es/dp/B0BZJE5L39"}
    ],
    "tablet": [
        {"name": "Samsung Galaxy Tab A9+ (Calidad)", "link": "https://www.amazon.es/dp/B0CL5C422L"},
        {"name": "Lenovo Tab M10 (Económica)", "link": "https://www.amazon.es/dp/B09VNFX272"}
    ],
    "ipad": [
        {"name": "iPad 2022 10.9 (Apple)", "link": "https://www.amazon.es/dp/B0BJLC6Z2M"}
    ],

    # --- AUDIO Y ORDENADORES ---
    "auriculares": [
        {"name": "Sony WH-CH520 (Calidad/Precio)", "link": "https://www.amazon.es/dp/B0BS1QCF54"},
        {"name": "Soundcore Q20i (Cancelación Ruido)", "link": "https://www.amazon.es/dp/B0C3HFE4X8"},
        {"name": "Sony WH-1000XM5 (Gama Alta)", "link": "https://www.amazon.es/dp/B09Y2MYL5C"}
    ],
    "inalambricos": [
        {"name": "Soundcore P20i (Top Ventas)", "link": "https://www.amazon.es/dp/B0BTYV49Y2"},
        {"name": "Xiaomi Redmi Buds 4 (Baratos)", "link": "https://www.amazon.es/dp/B0C39X5R5B"}
    ],
    "altavoz": [
        {"name": "JBL Flip 6 (Sonido Top)", "link": "https://www.amazon.es/dp/B09V7D322V"},
        {"name": "Anker Soundcore 3 (Económico)", "link": "https://www.amazon.es/dp/B08B8PG37S"}
    ],
    "portatil": [
        {"name": "HP 15s (Oficina/Estudios)", "link": "https://www.amazon.es/dp/B0C3R5L5L8"},
        {"name": "Lenovo IdeaPad Slim 3 (Oferta)", "link": "https://www.amazon.es/dp/B0C3R5L5L8"},
        {"name": "MacBook Air M1 (Premium)", "link": "https://www.amazon.es/dp/B08N5T6CZ6"}
    ],
    "monitor": [
        {"name": "MSI PRO MP243 (24\" IPS)", "link": "https://www.amazon.es/dp/B0B61XY598"},
        {"name": "BenQ GW2480 (Cuidado Ocular)", "link": "https://www.amazon.es/dp/B073NTCT4Q"}
    ],
    "raton": [
        {"name": "Logitech G502 HERO (Gaming)", "link": "https://www.amazon.es/dp/B07W7MQMD9"},
        {"name": "Logitech M185 (Sencillo)", "link": "https://www.amazon.es/dp/B004YD8CPO"}
    ],

    # --- HOGAR Y COCINA ---
    "freidora": [
        {"name": "Cosori 5.5L (La más vendida)", "link": "https://www.amazon.es/dp/B07N8N6C85"},
        {"name": "Cecotec Cecofry 6L (Barata)", "link": "https://www.amazon.es/dp/B09J1GLJCZ"}
    ],
    "air fryer": [
        {"name": "Cosori 5.5L", "link": "https://www.amazon.es/dp/B07N8N6C85"}
    ],
    "aspiradora": [
        {"name": "Roborock Q7 Max (Robot Top)", "link": "https://www.amazon.es/dp/B09S3RPY7W"},
        {"name": "Rowenta X-Pert (Escoba)", "link": "https://www.amazon.es/dp/B08N5H711V"},
        {"name": "Cecotec Conga (Económico)", "link": "https://www.amazon.es/dp/B08H93ZRLL"}
    ],
    "cafetera": [
        {"name": "Nespresso Inissia (Cápsulas)", "link": "https://www.amazon.es/dp/B00J65BBGY"},
        {"name": "Cecotec Power Espresso (Barista)", "link": "https://www.amazon.es/dp/B07GSTVFJK"}
    ],
    "batidora": [
        {"name": "Moulinex QuickChef (Potente)", "link": "https://www.amazon.es/dp/B075QDHYX9"},
        {"name": "Braun Minipimer (Clásica)", "link": "https://www.amazon.es/dp/B07T751N8J"}
    ],
    "sarten": [
        {"name": "Tefal Unlimited On (Anti-rayas)", "link": "https://www.amazon.es/dp/B08BR2W7D8"},
        {"name": "BRA Efficient (Lote 3)", "link": "https://www.amazon.es/dp/B003WOKJ9S"}
    ],
    "ventilador": [
        {"name": "Cecotec EnergySilence (Pie)", "link": "https://www.amazon.es/dp/B085GG74K2"},
        {"name": "Rowenta Turbo Silence (Silencioso)", "link": "https://www.amazon.es/dp/B01CJLA7C2"}
    ],

    # --- BELLEZA Y CUIDADO ---
    "cepillo": [
        {"name": "Oral-B Pro 3 (Recomendado)", "link": "https://www.amazon.es/dp/B095C2P93L"},
        {"name": "Philips Sonicare (Sónico)", "link": "https://www.amazon.es/dp/B09B8X98F3"}
    ],
    "afeitadora": [
        {"name": "Philips OneBlade (Cara/Cuerpo)", "link": "https://www.amazon.es/dp/B01BGH45Q0"},
        {"name": "Braun Series 5 (Eléctrica)", "link": "https://www.amazon.es/dp/B08H99BPJN"}
    ],
    "depiladora": [
        {"name": "Braun Silk-épil 9 (Rápida)", "link": "https://www.amazon.es/dp/B07T751N8J"},
        {"name": "Philips Lumea (Luz Pulsada)", "link": "https://www.amazon.es/dp/B08H93ZRLL"}
    ],
    "secador": [
        {"name": "Remington Ionic (Profesional)", "link": "https://www.amazon.es/dp/B003WOKJ9S"},
        {"name": "Parlux Advance (Alta Gama)", "link": "https://www.amazon.es/dp/B01CJLA7C2"}
    ],
    "creatina": [
        {"name": "Creatina Monohidrato (Pura)", "link": "https://www.amazon.es/dp/B002DYIZEO"}
    ],
    "proteina": [
        {"name": "Optimum Nutrition Whey", "link": "https://www.amazon.es/dp/B000QSNYGI"}
    ],

    # --- JUGUETES Y BEBÉ ---
    "lego": [
        {"name": "LEGO Star Wars (Top)", "link": "https://www.amazon.es/dp/B09Q471R78"},
        {"name": "LEGO Technic (Coches)", "link": "https://www.amazon.es/dp/B09Q4N5Z3J"}
    ],
    "playmobil": [
        {"name": "Playmobil City Life", "link": "https://www.amazon.es/dp/B0766CCV7L"}
    ],
    "pañales": [
        {"name": "Dodot Bebé-Seco (Mensual)", "link": "https://www.amazon.es/dp/B07Z8L3X9Z"},
        {"name": "Dodot Aqua Pure (Toallitas)", "link": "https://www.amazon.es/dp/B07CXVSK2V"}
    ],
    "silla coche": [
        {"name": "Cybex Solution (Segura)", "link": "https://www.amazon.es/dp/B005XR3KCA"}
    ],

    # --- VARIOS Y DEPORTES ---
    "taladro": [
        {"name": "Bosch Professional 12V", "link": "https://www.amazon.es/dp/B00D5U932W"},
        {"name": "Black+Decker (Hogar)", "link": "https://www.amazon.es/dp/B0114RJ7DG"}
    ],
    "mochila": [
        {"name": "Samsonite Guardit 2.0", "link": "https://www.amazon.es/dp/B07NHX3R35"},
        {"name": "Eastpak Padded (Escolar)", "link": "https://www.amazon.es/dp/B0001I1D2W"}
    ],
    "reloj": [
        {"name": "Amazfit GTS 4 Mini (Smart)", "link": "https://www.amazon.es/dp/B0B596F3V6"},
        {"name": "Casio G-SHOCK (Resistente)", "link": "https://www.amazon.es/dp/B000GAYQKY"}
    ],
    "mascota": [
         {"name": "Comida Perro Advance", "link": "https://www.amazon.es/dp/B01F3ELT2C"},
         {"name": "Arena Gatos Aglomerante", "link": "https://www.amazon.es/dp/B003V67A8Q"}
    ]
}

# --- LÓGICA DEL CEREBRO (IA) ---
def analizar_producto(brand="", title=""):
    score = 10
    reasons = []
    title_low = title.lower() if title else ""
    brand_clean = brand.replace("Visita la tienda de ", "").strip() if brand else "Genérico"
    
    is_vip_brand = False
    
    # 1. Comprobar MARCA VIP
    for vip in MARCAS_VIP:
        if vip in title_low or vip in brand_clean.lower():
            is_vip_brand = True
            break
            
    if is_vip_brand:
        score = 10
        veredicto = "Excelente Elección"
        detalles = "✅ Marca líder verificada. Compra segura."
    else:
        # 2. Análisis Técnico (Solo si no es VIP)
        if brand_clean.isupper() and len(brand_clean) < 10:
            score -= 4
            reasons.append("Marca genérica no reconocida.")
        if "http" not in title_low and len(title_low) > 250:
            score -= 2
            reasons.append("Título excesivamente largo.")
            
        if score >= 8:
            veredicto = "Producto Seguro"
            detalles = "✅ Análisis positivo. Puedes comprar con confianza."
        elif score >= 5:
            veredicto = "Precaución"
            detalles = " ".join(reasons) if reasons else "Faltan datos de fiabilidad."
        else:
            veredicto = "⚠️ Sospechoso"
            detalles = " ".join(reasons)

    # 3. Búsqueda de Recomendaciones (LISTA MULTI-OPCIÓN)
    lista_final = []
    
    for clave, lista_opciones in PRODUCTOS_TOP.items():
        if clave in title_low:
            # Encontramos la categoría, procesamos las opciones
            for opcion in lista_opciones:
                # Si el usuario ya ve este producto (si es VIP), lo saltamos
                if opcion["name"].lower().split()[0] in title_low and is_vip_brand:
                    continue 
                
                # Construcción del link con TAG
                link_base = opcion["link"]
                final_link = f"{link_base}&tag={AMAZON_TAG}" if "?" in link_base else f"{link_base}?tag={AMAZON_TAG}"
                
                lista_final.append({
                    "name": opcion["name"],
                    "link": final_link
                })
            
            if lista_final:
                break 

    # 4. Mensaje si NO encontramos nada (EL MENSAJE QUE PEDISTE)
    if not lista_final and not is_vip_brand and score < 7:
        return 0, "Sin Análisis", "⚠️ Lo sentimos; este producto aún no lo hemos analizado en nuestra base de datos.", []
    
    return score, veredicto, detalles, lista_final

# --- RUTA EXTENSIÓN (Chrome) ---
@app.post("/analyze")
async def analyze_ext(product: Product):
    score, veredicto, detalles, lista_recs = analizar_producto(product.brand, product.title)
    
    # La extensión mostrará la Opción 1 de la lista
    recomendacion_principal = lista_recs[0] if lista_recs else None
    
    return {
        "score": score,
        "reason": f"{veredicto}: {detalles}",
        "recommendation": recomendacion_principal
    }

# --- RUTA TELEGRAM (Multi-Opción) ---
async def start(update: Update, context):
    await update.message.reply_text("👋 ¡Hola! Soy TrustLens. Envíame un enlace de Amazon y te daré las mejores opciones.")

async def handle_msg(update: Update, context):
    user_text = update.message.text
    if "amazon" in user_text.lower() or "amzn" in user_text.lower():
        await update.message.reply_text("🕵️ Analizando producto...")
        
        score, veredicto, detalles, lista_recs = analizar_producto(brand="", title=user_text)
        
        # Caso especial: Producto no analizado y sospechoso
        if veredicto == "Sin Análisis":
             await update.message.reply_text(detalles)
             return

        msg = f"🔍 *Análisis TrustLens*\n\n📊 Veredicto: {veredicto}\n📝 {detalles}\n"
        
        if lista_recs:
            msg += "\n💡 *Mejores Alternativas (Haz clic para ver):*\n"
            for i, rec in enumerate(lista_recs, 1):
                msg += f"\n{i}. [{rec['name']}]({rec['link']})"
        
        await update.message.reply_markdown(msg)
    else:
        await update.message.reply_text("❌ Por favor, envía un enlace válido de Amazon.")

@app.on_event("startup")
async def startup_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    await application.initialize()
    await application.start()
    asyncio.create_task(application.updater.start_polling())
