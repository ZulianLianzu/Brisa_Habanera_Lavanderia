import os
import logging
import uuid
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

# ID del Administrador (CAMBIAR ESTO)
ADMIN_CHAT_ID = 8242379333 

# Base de datos simulada en memoria para guardar los pedidos activos
# Estructura: { ticket_id: { 'user_id': 123, 'name': 'Juan', 'delete_ids': [id1, id2...], 'ticket_msg_id': id_ticket, ... } }
pedidos_db = {}

# Precios Base
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
    "Habana del Este (Guanabo)": 1000,
    "Alamar (Zonas 9–11)": 1000,
}

# --- Estados de la Conversación ---
LOCATION, SERVICE_TYPE, EXPRESS_CONFIRM, QUANTITY, NAME, PHONE, ADDRESS, CONFIRM_PRE_TICKET = range(8)

# --- Generadores de Teclado ---

def get_location_keyboard():
    zonas = list(PRECIO_ZONA.keys())
    chunks = [zonas[i:i + 2] for i in range(0, len(zonas), 2)]
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

# --- Manejadores de Flujo del Usuario ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bienvenida y selección de Zona."""
    # Inicializar lista para guardar IDs de mensajes a borrar
    context.user_data['delete_ids'] = []
    
    welcome_msg = (
        "¡Bienvenido a Brisa Habanera! 🌬️\n\n"
        "Primero, necesitamos saber **tu ubicación** para asignar el servicio. "
        "Selecciona tu zona del menú inferior:"
    )
    msg = await update.message.reply_text(welcome_msg, reply_markup=get_location_keyboard())
    context.user_data['delete_ids'].append(msg.message_id)
    return LOCATION

async def location_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la zona y pregunta el servicio."""
    user_text = update.message.text

    if user_text == "❌ Cancelar pedido":
        return await cancel(update, context)
    
    if user_text in PRECIO_ZONA:
        context.user_data['location'] = user_text
        service_msg = (
            f"📍 Zona seleccionada: *{user_text}*\n\n"
            "Ahora selecciona el tipo de servicio:"
        )
        msg = await update.message.reply_text(
            service_msg, 
            parse_mode='Markdown', 
            reply_markup=get_services_keyboard()
        )
        context.user_data['delete_ids'].append(msg.message_id)
        return SERVICE_TYPE
    else:
        msg = await update.message.reply_text(
            "❌ Por favor, selecciona una zona válida del menú.",
            reply_markup=get_location_keyboard()
        )
        context.user_data['delete_ids'].append(msg.message_id)
        return LOCATION

async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de servicio."""
    query = update.callback_query
    await query.answer()

    if query.data == "lavado_normal":
        context.user_data['service'] = "Lavado y secado"
        context.user_data['is_express'] = False
        # NO agregamos el mensaje editado a la lista de borrar aquí, lo haremos en confirm
        await query.edit_message_text("✅ Servicio seleccionado: *Lavado y secado*\n\nIndica la cantidad aproximada de bolsas:", parse_mode='Markdown')
        return QUANTITY
    elif query.data == "express_check":
        warning_msg = (
            "⚠️ **ADVERTENCIA SERVICIO EXPRÉS** ⚠️\n\n"
            "El servicio exprés tiene un **recargo adicional del 50%** sobre el valor total del servicio.\n\n"
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
            "⚡ Servicio seleccionado: *Servicio exprés* (Recargo 50% aplicado)\n\nIndica la cantidad aproximada de bolsas:",
            parse_mode='Markdown'
        )
        return QUANTITY
    elif query.data == "cancel_flow":
        await query.edit_message_text("Pedido cancelado. Selecciona una zona para comenzar de nuevo.", reply_markup=get_location_keyboard())
        return LOCATION

async def quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['quantity'] = update.message.text
    msg = await update.message.reply_text("Perfecto. 📝 Escribe tu **Nombre**:")
    context.user_data['delete_ids'].append(msg.message_id)
    return NAME

async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    msg = await update.message.reply_text("Gracias. 📱 Escribe tu **Número de teléfono**:")
    context.user_data['delete_ids'].append(msg.message_id)
    return PHONE

async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['phone'] = update.message.text
    msg = await update.message.reply_text("📍 Por último, escribe tu **Dirección completa** (Calle, #, Apto, Ref):")
    context.user_data['delete_ids'].append(msg.message_id)
    return ADDRESS

async def address_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Calcula precio y muestra el PRE-BOLETO para confirmación."""
    address = update.message.text
    context.user_data['address'] = address
    
    # --- CÁLCULO DE PRECIO ---
    location = context.user_data.get('location')
    base_price = PRECIO_ZONA.get(location, 0)
    is_express = context.user_data.get('is_express', False)
    
    final_price = base_price
    if is_express:
        final_price = int(base_price * 1.5)
    
    context.user_data['final_price'] = final_price
    price_formatted = "{:,} CUP".format(final_price).replace(",", ".")

    # --- PRE-BOLETO ---
    pre_ticket_text = (
        f"🔍 *VERIFICACIÓN DE DATOS*\n\n"
        f"📍 Dirección: {address}\n"
        f"💰 Valor Mensajería: *{price_formatted}*\n\n"
        f"¿Son correctos estos datos para generar la orden?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Sí, Generar Boleto", callback_data="confirm_yes")],
        [InlineKeyboardButton("✏️ Corregir Dirección", callback_data="confirm_no_address")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(pre_ticket_text, parse_mode='Markdown', reply_markup=reply_markup)
    return CONFIRM_PRE_TICKET

async def process_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Genera el boleto final, lo guarda en DB, envía a admin y marca mensajes para limpiar."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no_address":
        # Volver a pedir dirección
        # Borramos el mensaje del pre-boleto para limpiar
        context.user_data['delete_ids'].append(query.message.message_id)
        await query.edit_message_text("Por favor, escribe nuevamente tu **Dirección completa**:")
        return ADDRESS
    
    if query.data == "confirm_yes":
        # 1. Generar ID Único
        ticket_id = uuid.uuid4().hex[:8].upper()
        
        # 2. Recuperar datos
        user_data = context.user_data
        location = user_data.get('location')
        final_price = user_data.get('final_price')
        price_formatted = "{:,} CUP".format(final_price).replace(",", ".")
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        user_id = update.effective_user.id

        # 3. Preparar lista de IDs a borrar (incluyendo el mensaje del pre-boleto)
        ids_to_delete = user_data.get('delete_ids', [])
        # Agregamos el ID del mensaje de pre-boleto que acabamos de editar
        ids_to_delete.append(query.message.message_id)

        # 4. Formatear Boleto Final
        ticket_text = (
            f"🧾 *BOLETO DE SERVICIO - BRISA HABANERA*\n"
            f"🆔 *ID:* {ticket_id}\n"
            f"---------------------------------\n"
            f"👤 *Cliente:* {user_data.get('name')}\n"
            f"📱 *Teléfono:* {user_data.get('phone')}\n"
            f"📍 *Dirección:* {user_data.get('address')}\n"
            f"🏙️ *Zona:* {location}\n"
            f"🧼 *Servicio:* {user_data.get('service')}\n"
            f"🧺 *Cantidad:* {user_data.get('quantity')} prendas\n"
            f"💰 *Mensajería:* {price_formatted}\n"
            f"📅 *Fecha:* {date_str}\n"
            f"🔄 *Estado:* Pendiente de recogida"
        )

        # 5. Borrar el mensaje de pre-boleto y botones antes de enviar el boleto
        # Esto deja el chat más limpio desde el inicio
        try:
            await query.edit_message_text("Generando tu boleto...")
        except:
            pass

        # 6. Enviar Boleto Final al Cliente
        ticket_msg = await context.bot.send_message(chat_id=user_id, text=ticket_text, parse_mode='Markdown')
        
        thanks_msg = (
            f"Gracias {user_data.get('name')}. Tu pedido ha sido registrado. "
            f"El equipo de Brisa Habanera te contactará pronto."
        )
        thanks_msg_obj = await context.bot.send_message(chat_id=user_id, text=thanks_msg, reply_markup=get_location_keyboard())
        
        # Agregamos el mensaje de "Gracias" a la lista para que también se borre
        ids_to_delete.append(thanks_msg_obj.message_id)

        # 7. Guardar en Base de Datos Simulada
        pedidos_db[ticket_id] = {
            'ticket_id': ticket_id,
            'user_id': user_id,
            'name': user_data.get('name'),
            'phone': user_data.get('phone'),
            'address': user_data.get('address'),
            'location': location,
            'service': user_data.get('service'),
            'quantity': user_data.get('quantity'),
            'price': price_formatted,
            'status': 'Pendiente de recogida',
            # Claves importantes para la limpieza:
            'delete_ids': ids_to_delete,          # Lista de mensajes chat que se borrarán
            'ticket_msg_id': ticket_msg.message_id # ID del boleto (NO borrar este)
        }

        # 8. Enviar al Administrador (con opciones de gestión)
        admin_msg = (
            f"🔔 **NUEVO PEDIDO RECIBIDO** 🔔\n\n"
            f"{ticket_text}"
        )
        admin_keyboard = [
            [InlineKeyboardButton("✅ Recibido", callback_data=f"adm_{ticket_id}_recibido")],
            [InlineKeyboardButton("👕 Ropa Lista", callback_data=f"adm_{ticket_id}_lista")],
            [InlineKeyboardButton("🏠 Entregado", callback_data=f"adm_{ticket_id}_entregado")]
        ]
        reply_markup_admin = InlineKeyboardMarkup(admin_keyboard)

        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID, 
                text=admin_msg,
                parse_mode='Markdown',
                reply_markup=reply_markup_admin
            )
        except Exception as e:
            logging.error(f"Error enviando mensaje al admin: {e}")

        # Limpiar datos de usuario por seguridad
        context.user_data.clear()
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Operación cancelada. Usa /start para comenzar de nuevo.",
        reply_markup=get_location_keyboard()
    )
    return ConversationHandler.END

# --- COMANDOS Y LÓGICA DE ADMINISTRADOR ---

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Tu ID de Telegram es: `{chat_id}`", parse_mode='Markdown')

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja los mensajes de texto enviados por el Admin.
    Si escribe un ID de boleto, muestra las opciones.
    """
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return

    text = update.message.text.strip().upper()
    
    if text in pedidos_db:
        pedido = pedidos_db[text]
        
        info_msg = (
            f"🔍 *Datos del Pedido {text}*\n\n"
            f"👤 Cliente: {pedido['name']}\n"
            f"📍 Dirección: {pedido['address']}\n"
            f"📱 Tel: {pedido['phone']}\n"
            f"📦 Estado Actual: {pedido['status']}\n\n"
            f"Selecciona una acción:"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Marcar como Recibido", callback_data=f"adm_{text}_recibido")],
            [InlineKeyboardButton("👕 Marcar como Ropa Lista", callback_data=f"adm_{text}_lista")],
            [InlineKeyboardButton("🏠 Marcar como Entregado", callback_data=f"adm_{text}_entregado")]
        ]
        await update.message.reply_text(info_msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(f"No se encontró un pedido activo con el ID: {text}")

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja los botones que presiona el admin.
    Borra mensajes antiguos del cliente y envía el nuevo estado.
    """
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_CHAT_ID:
        await query.edit_message_text("⛔ No tienes permisos para realizar esta acción.")
        return

    data = query.data.split('_') # adm_TICKETID_ACCION
    if len(data) != 3:
        return
    
    ticket_id = data[1]
    action = data[2]
    
    if ticket_id not in pedidos_db:
        await query.edit_message_text("❌ Este boleto ya no existe en el sistema (posiblemente fue borrado al reiniciar).")
        return

    pedido = pedidos_db[ticket_id]
    user_id = pedido['user_id']
    client_name = pedido['name']
    msg_to_admin = ""
    msg_to_client = ""

    # 1. LIMPIEZA DE CHAT DEL CLIENTE
    # Borramos todos los mensajes guardados en 'delete_ids' (Preguntas, Pre-boleto, etc.)
    ids_to_delete = pedido.get('delete_ids', [])
    
    for msg_id in ids_to_delete:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
        except Exception as e:
            # Ignoramos errores si el mensaje ya fue borrado o es muy viejo
            pass

    # 2. ACTUALIZAR ESTADO Y ENVIAR NUEVO MENSAJE
    if action == "recibido":
        pedido['status'] = "Recibido en Lavandería"
        msg_to_client = f"📢 Hola {client_name}, tu orden #{ticket_id} ha sido **RECIBIDA** por nuestros administradores, nos pondremos de acuerdo para la recogida."
        msg_to_admin = f"✅ Pedido #{ticket_id} marcado como RECIBIDO."
        
    elif action == "lista":
        pedido['status'] = "Lista para Entrega"
        msg_to_client = f"👕 ¡Hola {client_name}! Buenas noticias. Tu ropa (Orden #{ticket_id}) está **LISTA** y lista para ser entregada."
        msg_to_admin = f"👕 Pedido #{ticket_id} marcado como LISTO."
        
    elif action == "entregado":
        pedido['status'] = "Entregado al Cliente"
        msg_to_client = f"🏠 Hola {client_name}, confirmamos que tu orden #{ticket_id} ha sido **ENTREGADA**. ¡Gracias por confiar en Brisa Habanera!"
        msg_to_admin = f"🏠 Pedido #{ticket_id} marcado como ENTREGADO."

    # Enviar mensaje al cliente
    try:
        # Nota: Al enviar este mensaje, se queda arriba del boleto.
        await context.bot.send_message(chat_id=user_id, text=msg_to_client, parse_mode='Markdown')
        response_text = f"{msg_to_admin}\n\n✅ Chat del cliente limpiado y notificado."
    except Exception as e:
        logging.error(f"Error enviando notificación al cliente {user_id}: {e}")
        response_text = f"{msg_to_admin}\n\n❌ Error al enviar mensaje al cliente (quizás bloqueó el bot)."

    # Actualizar el mensaje del admin
    await query.edit_message_text(text=response_text, parse_mode='Markdown')


# --- Configuración Principal ---

def main() -> None:
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    
    if not TOKEN:
        logging.error("No se encontró TELEGRAM_TOKEN.")
        return

    application = Application.builder().token(TOKEN).build()

    # --- Manejador de Conversación ---
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
            CONFIRM_PRE_TICKET: [CallbackQueryHandler(process_confirmation)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    
    # --- Manejadores para el Admin ---
    application.add_handler(CommandHandler("mi_id", get_my_id))
    application.add_handler(MessageHandler(filters.TEXT & filters.Chat(ADMIN_CHAT_ID), admin_text_handler))
    application.add_handler(CallbackQueryHandler(admin_button_handler, pattern='^adm_'))

    # --- Iniciar Bot (Webhook o Polling) ---
    if os.environ.get("RENDER_EXTERNAL_URL"):
        webhook_url = os.environ.get("RENDER_EXTERNAL_URL") + "/webhook"
        application.bot.set_webhook(url=webhook_url)
        logging.info("Iniciando webhook...")
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8443)),
            url_path="webhook",
            webhook_url=webhook_url
        )
    else:
        logging.info("Iniciando polling...")
        application.run_polling()

if __name__ == "__main__":
    main()
