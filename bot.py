import logging
import threading
from telebot import TeleBot, types
import paypalrestsdk
from common import save_mapping

# Token reale del bot
TOKEN = "7745039187:AAEhlxK64Js4PsnXUlIK7Bbdl5rObgjbFbg"
bot = TeleBot(TOKEN)
logging.basicConfig(level=logging.DEBUG)

# Stato globale degli utenti
user_data = {}

def init_user_data(chat_id):
    if chat_id not in user_data:
        user_data[chat_id] = {
            "services": [],
            "current_service": None,
            "mode": "normal",
            "payment_in_progress": False,
            "order_completed": False
        }

def check_order_status(chat_id):
    if user_data.get(chat_id, {}).get("order_completed"):
        bot.send_message(chat_id, "L'ordine è già stato completato. Premi /start per iniziarne uno nuovo.")
        return True
    return False

def send_service_selection(chat_id):
    init_user_data(chat_id)
    if user_data[chat_id].get("order_completed"):
        bot.send_message(chat_id, "Per iniziare un nuovo ordine, premi /start.")
        return
    user_data[chat_id]["mode"] = "normal"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["📚 Lezioni", "🎙 Podcast", "🎤 Conferenze", "📋 Riepilogo", "❌ Rimuovi un servizio", "✔️ Concludi"]
    markup.add(*buttons)
    bot.send_message(chat_id, "Seleziona il servizio:", reply_markup=markup)

def format_duration(hours, minutes, seconds):
    parts = []
    if hours > 0:
        parts.append(f"{hours} ore" if hours > 1 else "1 ora")
    if minutes > 0:
        parts.append(f"{minutes} minuti" if minutes > 1 else "1 minuto")
    if seconds > 0:
        parts.append(f"{seconds} secondi" if seconds > 1 else "1 secondo")
    return " ".join(parts) if parts else "0 secondi"

def compute_price(service_type, delivery, total_minutes):
    if service_type == "📚 Lezioni":
        if total_minutes <= 120:
            if delivery == "Economico":
                return 0.25
            elif delivery == "Standard":
                return 0.40
            elif delivery == "Urgente":
                return 0.60
        else:
            if delivery == "Economico":
                return 0.20
            elif delivery == "Standard":
                return 0.30
            elif delivery == "Urgente":
                return 0.50
    elif service_type == "🎙 Podcast":
        if total_minutes <= 120:
            if delivery == "Standard":
                return 0.50
            elif delivery == "Urgente":
                return 0.70
        else:
            if delivery == "Standard":
                return 0.45
            elif delivery == "Urgente":
                return 0.60
    elif service_type == "🎤 Conferenze":
        if total_minutes <= 120:
            if delivery == "Standard":
                return 0.60
            elif delivery == "Urgente":
                return 0.80
        else:
            if delivery == "Standard":
                return 0.50
            elif delivery == "Urgente":
                return 0.70
    return 0.40

@bot.message_handler(commands=["start"])
def welcome(message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        "services": [],
        "current_service": None,
        "mode": "normal",
        "payment_in_progress": False,
        "order_completed": False
    }
    pricing_text = (
        "Benvenuto/a su 'Appunti Perfetti – Trascrizioni Veloci e Accurate'!\n\n"
        "Hai bisogno di trascrivere lezioni, conferenze o altri contenuti audio?\n"
        "Scegli il servizio e segui le istruzioni per procedere."
    )
    bot.send_message(chat_id, pricing_text)
    send_service_selection(chat_id)

@bot.message_handler(func=lambda message: message.text and message.text.strip() in ["📚 Lezioni", "🎙 Podcast", "🎤 Conferenze"])
def select_service(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    if check_order_status(chat_id):
        return
    user_data[chat_id]["current_service"] = {"name": message.text.strip()}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    if message.text.strip() == "📚 Lezioni":
        buttons = ["Economico", "Standard", "Urgente", "🔙 Indietro"]
    else:
        buttons = ["Standard", "Urgente", "🔙 Indietro"]
    markup.add(*buttons)
    bot.send_message(chat_id, "Ora scegli la modalità di consegna:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and message.text.strip() == "🔙 Indietro")
def go_back(message):
    chat_id = message.chat.id
    if check_order_status(chat_id):
        return
    init_user_data(chat_id)
    send_service_selection(chat_id)

@bot.message_handler(func=lambda message: message.text and message.text.strip() in ["Economico", "Standard", "Urgente"])
def select_delivery(message):
    chat_id = message.chat.id
    if check_order_status(chat_id):
        return
    init_user_data(chat_id)
    if not user_data[chat_id]["current_service"]:
        bot.send_message(chat_id, "⚠️ Nessun servizio selezionato. Seleziona un servizio prima.")
        return
    user_data[chat_id]["current_service"]["delivery"] = message.text.strip()
    bot.send_message(chat_id, "Inserisci la durata in formato HH:MM:SS:")

@bot.message_handler(func=lambda message: message.text and ':' in message.text)
def insert_duration(message):
    chat_id = message.chat.id
    if check_order_status(chat_id):
        return
    init_user_data(chat_id)
    current = user_data[chat_id]["current_service"]
    if not current or "delivery" not in current:
        bot.send_message(chat_id, "⚠️ Seleziona la modalità di consegna prima di inserire la durata.")
        return
    try:
        hours, minutes, seconds = map(int, message.text.strip().split(':'))
        duration_text = format_duration(hours, minutes, seconds)
        total_minutes = hours * 60 + minutes + seconds / 60
        price_per_min = compute_price(current["name"], current["delivery"], total_minutes)
        total_price = total_minutes * price_per_min
        current["duration"] = duration_text
        current["price"] = total_price
        current["file_requested"] = True
        bot.send_message(chat_id, f"✅ Durata registrata! Totale: €{total_price:.2f}\nOra invia il file da caricare su Google Drive.")
    except ValueError:
        bot.send_message(chat_id, "⚠️ Formato non valido. Usa HH:MM:SS.")

def process_file(chat_id):
    current = user_data[chat_id]["current_service"]
    if not current or "file_message" not in current:
        return
    if current.get("multiple_files", False):
        return
    bot.send_message(chat_id, "Il file sta venendo caricato, attendi qualche secondo...")
    file_doc = current["file_message"]
    file_path = f"./{file_doc.file_name}"
    file_info = bot.get_file(file_doc.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open(file_path, "wb") as new_file:
        new_file.write(downloaded_file)
    # Sostituisci con la logica di upload, se necessario
    result = "✅ File caricato correttamente"
    if result.startswith("✅"):
        current["file"] = file_doc.file_name
        bot.send_message(chat_id, "✅ File caricato correttamente!")
        user_data[chat_id]["services"].append(current)
        user_data[chat_id]["current_service"] = None
        send_service_selection(chat_id)
    else:
        bot.send_message(chat_id, "⚠️ Errore nel caricamento. Riprova inviando il file di nuovo.")
    current.pop("file_message", None)
    current.pop("file_timer", None)
    current.pop("file_requested", None)

@bot.message_handler(content_types=["document"])
def handle_document(message):
    chat_id = message.chat.id
    if check_order_status(chat_id):
        return
    init_user_data(chat_id)
    current = user_data[chat_id]["current_service"]
    if not current or not current.get("file_requested", False):
        bot.send_message(chat_id, "⚠️ In questo momento non è richiesto l'invio di un file.")
        return
    if "file_message" in current:
        if current["file_message"].file_id == message.document.file_id:
            return
        else:
            current["multiple_files"] = True
            if "file_timer" in current:
                timer = current.pop("file_timer", None)
                if timer:
                    timer.cancel()
            bot.send_message(chat_id, "⚠️ Hai inviato più di un file. Invia un solo file per favore.")
            current.pop("file_message", None)
            return
    current["file_message"] = message.document
    current["multiple_files"] = False
    timer = threading.Timer(3.0, process_file, args=(chat_id,))
    current["file_timer"] = timer
    timer.start()

@bot.message_handler(func=lambda message: message.text and message.text.strip() == "❌ Rimuovi un servizio")
def remove_service(message):
    chat_id = message.chat.id
    if check_order_status(chat_id):
        return
    init_user_data(chat_id)
    user_data[chat_id]["mode"] = "remove"
    if not user_data[chat_id]["services"]:
        bot.send_message(chat_id, "⚠️ Non hai servizi da rimuovere.")
        user_data[chat_id]["mode"] = "normal"
        return
    text = "Scrivi il numero del servizio da rimuovere:\n"
    for idx, service in enumerate(user_data[chat_id]["services"]):
        delivery = service.get("delivery", "N/A")
        text += f"{idx+1}. {service['name']} - {delivery} ({service.get('duration','N/A')})\n"
    bot.send_message(chat_id, text)

@bot.message_handler(func=lambda message: message.text and message.text.strip().isdigit() and user_data.get(message.chat.id, {}).get("mode") == "remove")
def confirm_remove_service(message):
    chat_id = message.chat.id
    if check_order_status(chat_id):
        return
    init_user_data(chat_id)
    idx = int(message.text.strip()) - 1
    if 0 <= idx < len(user_data[chat_id]["services"]):
        removed_service = user_data[chat_id]["services"].pop(idx)
        bot.send_message(chat_id, f"❌ Servizio rimosso: {removed_service['name']} - {removed_service.get('delivery','N/A')}")
    else:
        bot.send_message(chat_id, "⚠️ Numero non valido.")
    user_data[chat_id]["mode"] = "normal"
    show_summary(message)

@bot.message_handler(func=lambda message: message.text and message.text.strip() == "📋 Riepilogo")
def show_summary(message):
    chat_id = message.chat.id
    if check_order_status(chat_id):
        return
    init_user_data(chat_id)
    if not user_data[chat_id]["services"]:
        bot.send_message(chat_id, "⚠️ Non hai ancora aggiunto servizi.")
        return
    text = "📋 Riepilogo Ordine:\n"
    total_price = sum(s["price"] for s in user_data[chat_id]["services"])
    for idx, service in enumerate(user_data[chat_id]["services"]):
        text += f"{idx+1}. {service['name']} - {service.get('delivery','N/A')}\n   ⏳ {service.get('duration','N/A')} → 💰 €{service['price']:.2f}\n"
    text += f"\n💰 Totale: €{total_price:.2f}"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💳 Paga con PayPal", "❌ Annulla Ordine")
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and message.text.strip() == "✔️ Concludi")
def conclude_order(message):
    chat_id = message.chat.id
    if check_order_status(chat_id):
        return
    init_user_data(chat_id)
    total_price = sum(s["price"] for s in user_data[chat_id]["services"])
    if total_price == 0:
        bot.send_message(chat_id, "⚠️ Nessun servizio selezionato per il pagamento.")
        send_service_selection(chat_id)
        return
    text = "✨ Ordine Concluso!\n📋 Riepilogo Ordine:\n"
    for idx, service in enumerate(user_data[chat_id]["services"]):
        text += f"{idx+1}. {service['name']} - {service.get('delivery','N/A')}\n   ⏳ {service.get('duration','N/A')} → 💰 €{service['price']:.2f}\n"
    text += f"\n💰 Totale: €{total_price:.2f}\n\nSe vuoi procedere con il pagamento, clicca su '💳 Paga con PayPal'."
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💳 Paga con PayPal", "❌ Annulla Ordine")
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and message.text.strip() == "❌ Annulla Ordine")
def cancel_order(message):
    chat_id = message.chat.id
    if check_order_status(chat_id):
        return
    init_user_data(chat_id)
    user_data[chat_id] = {
        "services": [],
        "current_service": None,
        "mode": "normal",
        "payment_in_progress": False,
        "order_completed": False
    }
    bot.send_message(chat_id, "❌ Ordine annullato. Premi /start per iniziare un nuovo ordine.")

@bot.message_handler(func=lambda message: message.text and message.text.strip() == "💳 Paga con PayPal")
def pay_with_paypal(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    if user_data[chat_id].get("order_completed"):
        bot.send_message(chat_id, "Il pagamento è già stato completato. Premi /start per iniziare un nuovo ordine.")
        return
    if user_data[chat_id].get("payment_in_progress"):
        bot.send_message(chat_id, "Il pagamento è in corso, attendi il completamento.")
        return
    if not user_data[chat_id].get("services"):
        bot.send_message(chat_id, "⚠️ Ordine non trovato. Premi /start per iniziare un nuovo ordine.")
        return

    total_price = sum(s["price"] for s in user_data[chat_id]["services"])
    if total_price <= 0:
        bot.send_message(chat_id, "⚠️ Non ci sono servizi da pagare.")
        return

    user_data[chat_id]["payment_in_progress"] = True

    payment = paypalrestsdk.Payment({
       "intent": "sale",
       "payer": {"payment_method": "paypal"},
       "redirect_urls": {
           "return_url": "https://paypal-server-bafg.onrender.com/payment/execute",
           "cancel_url": "https://paypal-server-bafg.onrender.com/payment/cancel"
       },
       "transactions": [{
           "item_list": {
               "items": [{
                   "name": "Servizi Bot",
                   "sku": "001",
                   "price": f"{total_price:.2f}",
                   "currency": "EUR",
                   "quantity": 1
               }]
           },
           "amount": {
               "total": f"{total_price:.2f}",
               "currency": "EUR"
           },
           "description": "Pagamento per i servizi offerti dal bot.",
           "custom": str(chat_id)
       }]
    })

    logging.debug("Creazione pagamento...")
    if payment.create():
        logging.debug("Pagamento creato, payment.id = %s", payment.id)
        # Utilizziamo getattr per leggere eventuale debug_id
        debug_id = getattr(payment, "debug_id", None)
        if debug_id:
            logging.debug("PayPal debug_id: %s", debug_id)
        save_mapping(payment.id, str(chat_id))
        approval_url = None
        for link in payment.links:
            logging.debug("Link trovato: %s - %s", link.rel, link.href)
            if link.rel == "approval_url":
                approval_url = str(link.href)
                break
        if approval_url:
            bot.send_message(chat_id, f"Per completare il pagamento, clicca su questo link:\n{approval_url}")
        else:
            bot.send_message(chat_id, "⚠️ Errore: Impossibile ottenere il link di approvazione.")
            user_data[chat_id]["payment_in_progress"] = False
    else:
        error_info = payment.error
        logging.error("Errore nella creazione del pagamento: %s", error_info)
        bot.send_message(chat_id, f"⚠️ Errore nella creazione del pagamento: {error_info}")
        user_data[chat_id]["payment_in_progress"] = False

if __name__ == '__main__':
    bot.polling(none_stop=True)

