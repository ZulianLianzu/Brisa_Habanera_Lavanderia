import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# --- Estados de la Conversación ---
SERVICE, QUANTITY, NAME, PHONE, ADDRESS = range(5)

# --- Teclados (Keyboards) ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🧺 Solicitar servicio", callback_data="solicitar")],
        [InlineKeyboardButton("📋 Ver precios", callback_data="precios")],
        [InlineKeyboardButton("📞 Contacto", callback_data="contacto")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_services_keyboard():
    keyboard = [
        [InlineKeyboardButton("Lavado y secado", callback_data="lavado_secado")],
        [InlineKeyboardButton("Servicio exprés", callback_data="express")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Manejadores de Comandos y Flujo ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bienvenida inicial y menú principal."""
    welcome_message = (
        "¡Bienvenido a Brisa Habanera! 🌬️\n\n"
        "Tu ropa limpia y fresca sin complicaciones. "
        "Selecciona una opción para comenzar."
    )
    await update.message.reply_text(
        welcome_message,
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la navegación desde los botones del menú principal."""
    query = update.callback_query
    await query.answer()

    if query.data == "solicitar":
        # Iniciar flujo de pedido
        services_message = "Selecciona el tipo de servicio que deseas:"
        await query.edit_message_text(
            services_message,
            reply_markup=get_services_keyboard()
        )
        return SERVICE
    
    elif query.data == "precios":
        prices_text = (
            "📋 **Lista de Precios:**\n\n"
            "• Lavado y secado: $X por libra/kilo\n"
            "• Servicio exprés: $Y (Entrega en 24h)\n\n"
            "¿Te gustaría solicitar un servicio?"
        )
        # Volvemos a mostrar el menú principal para que puedan actuar
        await query.edit_message_text(prices_text, reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

    elif query.data == "contacto":
        contact_text = (
            "📞 **Información de Contacto:**\n\n"
            "📍 Dirección: La Habana, Cuba\n"
            "📧 Email: contacto@brisahabanera.com\n"
            "📱 Teléfono: +53 555-0000\n\n"
            "Estamos para servirte. 🌬️"
        )
        await query.edit_message_text(contact_text, reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el servicio seleccionado y pide cantidad."""
    query = update.callback_query
    await query.answer()
    
    service_name = "Lavado y secado" if query.data == "lavado_secado" else "Servicio exprés"
    context.user_data['service'] = service_name
    
    await query.edit_message_text(
        f"✅ Servicio seleccionado: *{service_name}*\n\n"
        "Indica la cantidad aproximada de prendas (ej: 5, 10, una bolsa):",
        parse_mode='Markdown'
    )
    return QUANTITY

async def quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la cantidad y pide el nombre."""
    quantity = update.message.text
    context.user_data['quantity'] = quantity
    
    await update.message.reply_text("Perfecto. Ahora, por favor, escribe tu **Nombre completo**:")
    return NAME

async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nombre y pide el teléfono."""
    name = update.message.text
    context.user_data['name'] = name
    
    await update.message.reply_text(
        f"Gracias, {name}. 📝\n\n"
        "Proporciona tu **Número de teléfono** (con código de país si es posible):"
    )
    return PHONE

async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el teléfono y pide la dirección."""
    phone = update.message.text
    context.user_data['phone'] = phone
    
    await update.message.reply_text(
        "Excelente. 📍\n\n"
        "Por último, escribe tu **Dirección completa**:\n"
        "(Calle, número, apto, barrio y referencia cercana)"
    )
    return ADDRESS

async def address_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Genera el boleto final y termina la conversación."""
    address = update.message.text
    context.user_data['address'] = address
    
    # Recuperar datos
    data = context.user_data
    name = data.get('name', 'Cliente')
    service = data.get('service', 'General')
    quantity = data.get('quantity', '0')
    
    # Fecha actual
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Crear Boleto
    ticket_text = (
        f"🧾 *Boleto de servicio - Brisa Habanera*\n\n"
        f"👤 *Cliente:* {name}\n"
        f"📱 *Teléfono:* {data.get('phone')}\n"
        f"📍 *Dirección:* {address}\n"
        f"🧼 *Servicio:* {service}\n"
        f"🧺 *Cantidad:* {quantity}\n"
        f"📅 *Fecha:* {date_str}\n"
        f"🔄 *Estado:* Pendiente de recogida"
    )
    
    final_message = (
        f"{ticket_text}\n\n"
        f"¡Gracias {name}! Tu pedido ha sido registrado. "
        f"Nuestro equipo pasará a recoger tu ropa según disponibilidad. "
        f"Te contactaremos al número proporcionado."
    )
    
    # Enviar el boleto y limpiar datos
    await update.message.reply_text(final_message, parse_mode='Markdown')
    
    # Opcional: Limpiar datos del usuario para privacidad
    context.user_data.clear()
    
    # Mostrar menú principal de nuevo
    await update.message.reply_text(
        "¿Deseas realizar algo más?",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la conversación y vuelve al inicio."""
    await update.message.reply_text(
        "Operación cancelada. Si necesitas ayuda, escribe /start.",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

# --- Configuración Principal ---

def main() -> None:
    # Obtener Token de las Variables de Entorno
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    PORT = int(os.environ.get("PORT", 8443))
    
    if not TOKEN:
        logging.error("No se encontró la variable de entorno TELEGRAM_TOKEN.")
        return

    # Crear la Aplicación
    application = Application.builder().token(TOKEN).build()

    # Manejador de Conversación para el flujo de pedido
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(main_menu_handler, pattern='^solicitar$')],
        states={
            SERVICE: [CallbackQueryHandler(service_selected)],
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, quantity_received)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_received)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Registrar handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(main_menu_handler, pattern='^(precios|contacto)$'))
    application.add_handler(conv_handler)

    # Configurar Webhook para Render
    # Render asigna automáticamente una URL. Usamos una ruta relativa.
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL") + "/webhook"
    
    # En producción, establecer el webhook
    if os.environ.get("RENDER_EXTERNAL_URL"):
        application.bot.set_webhook(url=webhook_url)
    
    # Iniciar el servidor
    logging.info("Iniciando bot...")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    main()
