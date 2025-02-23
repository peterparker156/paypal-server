import logging
import threading
from telebot import TeleBot, types
import paypalrestsdk

# Imposta il livello di log (DEBUG per troubleshooting)
logging.basicConfig(level=logging.DEBUG)

# Token reale del bot
TOKEN = "7745039187:AAEhlxK64Js4PsnXUlIK7Bbdl5rObgjbFbg"
bot = TeleBot(TOKEN)

# Stato globale degli utenti
user_data = {}

def init_user_data(chat_id):
    if chat_id not in user_data:
        user_data[chat_id] = {'services': [], 'current_service': None, 'mode': 'normal'}

def upload_to_drive(file_path, chat_id):
    try:
        # Inserisci qui la logica per caricare il file su Google Drive
        return "✅ File caricato correttamente"
    except Exception as e:
        return f"⚠️ Errore durante il caricamento: {e}"

def send_service_selection(chat_id):
    init_user_data(chat_id)
    user_data[chat_id]['mode'] = 'normal'
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

###############################################
# FUNZIONE PER NOTIFICARE L'UTENTE (AGGIORNATA)
###############################################
def notify_user_payment_success(chat_id):
    try:
        logging.debug("Invio notifica di successo a chat_id: %s", chat_id)
        markup = types.ReplyKeyboardRemove()
        bot.send_message(
            chat_id,
            "Il tuo pagamento è stato confermato. L'ordine è andato a buon fine. Grazie per aver acquistato i nostri servizi!\n\nPer iniziare un nuovo ordine, premi /start.",
            reply_markup=markup
        )
    except Exception as e:
        logging.error("Errore durante la notifica dell'utente %s: %s", chat_id, e)
    if chat_id in user_data:
        logging.debug("Stato ordine prima del reset per chat_id %s: %s", chat_id, user_data[chat_id])
        del user_data[chat_id]
    init_user_data(chat_id)
    logging.debug("Stato dopo il reset per chat_id %s: %s", chat_id, user_data[chat_id])

###############################################
# HANDLER DEL BOT
###############################################
@bot.message_handler(commands=['start'])
def welcome(message):
    chat_id = message.chat.id
    # Reset dell'ordine per ogni comando /start
    user_data[chat_id] = {'services': [], 'current_service': None, 'mode': 'normal'}
    pricing_text = (
        "Benvenuto/a su \"Appunti Perfetti – Trascrizioni Veloci e Accurate\"!\n\n"
        "Hai bisogno di trascrivere lezioni universitarie, corsi, conferenze o altri contenuti audio? "
        "Appunti Perfetti ti offre trascrizioni rapide, precise e a prezzi vantaggiosi.\n\n"
        "Cosa facciamo:\n"
        "🔹 Lezioni universitarie e corsi\n"
        "🔹 Podcast e interviste\n"
        "🔹 Conferenze e webinar\n\n"
        "Prezzi:\n"
        "● Lezioni Universitarie e Corsi\n"
        "   Economico: €0,25/min (1 settimana) | Standard: €0,40/min (48 ore) | Urgente: €0,60/min (24 ore)\n"
        "   Ordini >2 ore: Economico: €0,20/min | Standard: €0,30/min | Urgente: €0,50/min\n\n"
        "● Podcast e Interviste\n"
        "   Standard: €0,50/min (48 ore) | Urgente: €0,70/min (24 ore)\n"
        "   Ordini >2 ore: Standard: €0,45/min | Urgente: €0,60/min\n\n"
        "● Conferenze e Webinar\n"
        "   Standard: €0,60/min (48 ore) | Urgente: €0,80/min (24 ore)\n"
        "   Ordini >2 ore: Standard: €0,50/min | Urgente: €0,70/min\n\n"
    )
    bot.send_message(chat_id, pricing_text)
    send_service_selection(chat_id)

# ... [qui seguono tutti gli altri handler come nel file precedente] ...

###############################################
# HANDLER PER IL PAGAMENTO CON PAYPAL
###############################################
@bot.message_handler(func=lambda message: message.text == "💳 Paga con PayPal")
def pay_with_paypal(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    total_price = sum(s['price'] for s in user_data[chat_id]['services'])
    if total_price <= 0:
        bot.send_message(chat_id, "⚠️ Non ci sono servizi da pagare.")
        return

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
        from server import save_mapping  # Importazione ritardata
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
    else:
        bot.send_message(chat_id, f"⚠️ Errore nella creazione del pagamento: {payment.error}")

# Avvio del bot in produzione
if __name__ == '__main__':
    bot.polling(none_stop=True)
