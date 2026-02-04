import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Configuración de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- CONFIGURACIÓN Y DATOS ---

# Aquí debes poner el ID numérico del administrador. 
# Para saberlo, el administrador debe usar el comando /mi_id en el bot.
ADMIN_CHAT_ID = "52946005"  # <--- AQUÍ VA EL ID DEL ADMIN (Ejemplo: 123456789)

# Precios Base (Extraídos de tu tabla)
# Estos son los precios para servicio normal (Lavado y Secado)
PRECIO_ZONA = {
    "Centro Habana": 720,
    "Vedado (hasta Paseo)": 780,
    "Vedado (después de Paseo)": 840,
    "Habana Vieja": 660,
    "Cerro": 600,
    "Nuevo Vedado": 840,
    "Playa (Puente de Hierro – Calle 60)": 1000,
    "Playa (Calle 60 – Paradero)": 1000,
    "Siboney": 1000,
    "Jaimanita": 1000,
    "Santa Fe": 1000,
    "Marianao (ITM)": 960,
    "Marianao (100 y 51)": 1000,
    "Boyeros (Aeropuerto)": 600,
    "Arroyo Naranjo (Los Pinos)": 300,
    "Arroyo Naranjo (Mantilla)": 360,
    "Arroyo Naranjo (Calvario)": 480,
    "Arroyo Naranjo (Eléctrico)": 540,
    "Diez de Octubre (Santo Suárez)": 420,
    "Diez de Octubre (Lawton)": 540,
    "San Miguel del Padrón (Virgen del Camino)": 720,
    "Cotorro (Puente)": 900,
    "Habana del Este (Regla)": 780,
    "Habana del Este (Guanabo)": 1000, # Base 2100 pero tope 1000 según tabla
    "Alamar (Zonas 9–11)": 1000, # Base 1080 pero tope 1000 según tabla
}

# --- Estados de la Conversación ---
LOCATION, SERVICE_TYPE, EXPRESS_CONFIRM, QUANTITY, NAME, PHONE, ADDRESS = range(7)

# --- Generadores de Teclado ---

def get_location_keyboard():
    """Crea un teclado con las zonas ordenadas."""
    zonas = list(PRECIO_ZONA.keys())
    # Agrupamos en listas de 2 para que se vea ordenado
    chunks = [zonas[i:i + 2] for i in range(0, len(zonas), 2)]
    # Agregamos botón de cancelar al final
    chunks.append(["❌ Cancelar pedido"])
    return ReplyKeyboardMarkup(chunks, resize_keyboard=True, one_time_keyboard=True)

def get_services_keyboard():
    keyboard = [
        [InlineKeyboardButton("🧺 Lavado y secado (Normal)", callback_data="lavado_normal")],
        [InlineKeyboardButton("⚡ Servicio exprés", callback_data="express_check")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirm_express_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Sí, continuar (+50%)", callback_data="express_yes")],
        [InlineKeyboardButton("❌ No, cancelar", callback_data="cancel_flow")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Manejadores de Flujo ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bienvenida y selección de Zona."""
    welcome_msg = (
        "¡Bienvenido a Brisa Habanera! 🌬️\n\n"
        "Primero, necesitamos saber **tu ubicación** para asignar el servicio. "
        "Selecciona tu zona del menú inferior:"
    )
    await update.message.reply_text(welcome_msg, reply_markup=get_location_keyboard())
    return LOCATION

async def location_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la zona y pregunta el servicio."""
    user_text = update.message.text

    if user_text == "❌ Cancelar pedido":
        return await cancel(update, context)
    
    # Verificar si la zona existe en nuestra lista
    if user_text in PRECIO_ZONA:
        context.user_data['location'] = user_text
        
        service_msg = (
            f"📍 Zona seleccionada: *{user_text}*\n\n"
            "Ahora selecciona el tipo de servicio:"
        )
        await update.message.reply_text(
            service_msg, 
            parse_mode='Markdown', 
            reply_markup=get_services_keyboard()
        )
        return SERVICE_TYPE
    else:
        await update.message.reply_text(
            "❌ Por favor, selecciona una zona válida del menú.",
            reply_markup=get_location_keyboard()
        )
        return LOCATION

async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de servicio."""
    query = update.callback_query
    await query.answer()

    if query.data == "lavado_normal":
        context.user_data['service'] = "Lavado y secado"
        context.user_data['is_express'] = False
        await query.edit_message_text("✅ Servicio seleccionado: *Lavado y secado*\n\nIndica la cantidad aproximada de prendas:", parse_mode='Markdown')
        return QUANTITY

    elif query.data == "express_check":
        # Mostrar advertencia de Express
        warning_msg = (
            "⚠️ **ADVERTENCIA SERVICIO EXPRÉS** ⚠️\n\n"
            "El servicio exprés tiene un **recargo adicional del 50%** sobre el valor del trayecto por zona.\n\n"
            "¿Estás de acuerdo y deseas continuar?"
        )
        await query.edit_message_text(warning_msg, reply_markup=get_confirm_express_keyboard())
        return EXPRESS_CONFIRM

async def express_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la confirmación del servicio exprés."""
    query = update.callback_query
    await query.answer()

    if query.data == "express_yes":
        context.user_data['service'] = "Servicio exprés"
        context.user_data['is_express'] = True
        await query.edit_message_text(
            "⚡ Servicio seleccionado: *Servicio exprés* (Recargo 50% aplicado)\n\nIndica la cantidad aproximada de prendas:",
            parse_mode='Markdown'
        )
        return QUANTITY
    elif query.data == "cancel_flow":
        # Volver al inicio
        await query.edit_message_text("Pedido cancelado. Selecciona una zona para comenzar de nuevo.", reply_markup=get_location_keyboard())
        return LOCATION

async def quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda cantidad y pide nombre."""
    context.user_data['quantity'] = update.message.text
    await update.message.reply_text("Perfecto. 📝 Escribe tu **Nombre completo**:")
    return NAME

async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda nombre y pide teléfono."""
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Gracias. 📱 Escribe tu **Número de teléfono**:")
    return PHONE

async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda teléfono y pide dirección."""
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("📍 Por último, escribe tu **Dirección completa** (Calle, #, Apto, Ref):")
    return ADDRESS

async def address_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Calcula precio, genera boleto, envía a usuario y admin."""
    address = update.message.text
    context.user_data['address'] = address
    
    # --- CÁLCULO DE PRECIO ---
    location = context.user_data.get('location')
    base_price = PRECIO_ZONA.get(location, 0)
    
    is_express = context.user_data.get('is_express', False)
    service_name = context.user_data.get('service', 'General')
    
    final_price = base_price
    if is_express:
        final_price = int(base_price * 1.5)
    
    price_formatted = "{:,} CUP".format(final_price).replace(",", ".")

    # --- GENERACIÓN BOLETO ---
    user_data = context.user_data
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    ticket_text = (
        f"🧾 *BOLETO DE SERVICIO - BRISA HABANERA*\n"
        f"---------------------------------\n"
        f"👤 *Cliente:* {user_data.get('name')}\n"
        f"📱 *Teléfono:* {user_data.get('phone')}\n"
        f"📍 *Dirección:* {address}\n"
        f"🏙️ *Zona:* {location}\n"
        f"🧼 *Servicio:* {service_name}\n"
        f"🧺 *Cantidad:* {user_data.get('quantity')} prendas\n"
        f"💰 *TOTAL A PAGAR:* {price_formatted}\n"
        f"📅 *Fecha:* {date_str}\n"
        f"🔄 *Estado:* Pendiente de recogida"
    )

    # 1. Enviar al Cliente
    await update.message.reply_text(ticket_text, parse_mode='Markdown')
    
    thanks_msg = (
        f"¡Gracias {user_data.get('name')}! Tu pedido ha sido registrado. "
        f"El equipo de Brisa Habanera te contactará pronto."
    )
    await update.message.reply_text(thanks_msg, reply_markup=get_location_keyboard())

    # 2. Enviar al Administrador
    try:
        # Nota: ADMIN_CHAT_ID debe ser un número (int) o string válido del ID del usuario.
        # Si pusiste el teléfono +53... en la variable arriba, esto fallará.
        # Revisa la nota al inicio del código.
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, 
            text=f"🔔 **NUEVO PEDIDO RECIBIDO** 🔔\n\n{ticket_text}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Error enviando mensaje al admin: {e}")

    # Limpiar datos para privacidad
    context.user_data.clear()
    return LOCATION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la conversación."""
    await update.message.reply_text(
        "Operación cancelada. Usa /start para comenzar de nuevo.",
        reply_markup=get_location_keyboard()
    )
    return ConversationHandler.END

# --- COMANDO DE UTILIDAD PARA EL ADMIN ---
async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """El admin usa este comando para saber su ID numérico."""
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Tu ID de Telegram es: `{chat_id}`\nCopia este número y pégalo en el código como ADMIN_CHAT_ID.", parse_mode='Markdown')

# --- Configuración Principal ---

def main() -> None:
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    PORT = int(os.environ.get("PORT", 8443))
    
    if not TOKEN:
        logging.error("No se encontró TELEGRAM_TOKEN.")
        return

    application = Application.builder().token(TOKEN).build()

    # Manejador de Conversación Completo
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, location_selected)],
            SERVICE_TYPE: [CallbackQueryHandler(service_selected)],
            EXPRESS_CONFIRM: [CallbackQueryHandler(express_confirmed)],
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, quantity_received)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_received)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("mi_id", get_my_id))

    # Configurar Webhook
    if os.environ.get("RENDER_EXTERNAL_URL"):
        webhook_url = os.environ.get("RENDER_EXTERNAL_URL") + "/webhook"
        application.bot.set_webhook(url=webhook_url)
    
    logging.info("Iniciando bot...")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    main()
