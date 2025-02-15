import os
import threading
import time
import telebot
from telebot import types
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import paypalrestsdk  # Per la gestione dei pagamenti

# Configurazione del bot Telegram (usa il tuo token)
API_TOKEN = '7745039187:AAEhlxK64Js4PsnXUlIK7Bbdl5rObgjbFbg'
bot = telebot.TeleBot(API_TOKEN)

# Configurazione di Google Drive
SERVICE_ACCOUNT_FILE = 'appuntiperfetti.json'  # Percorso al file JSON dell'account di servizio
SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = "1--TOQVt0viBsnRLWto8m9EPKUkCT62om"

# Dizionari per i dati utente e per il mapping payment_id -> chat_id
user_data = {}
orders_mapping = {}  # Mapping per associare payment_id a chat_id (usato per PayPal)

# Configurazione di PayPal (sostituisci i placeholder con le tue credenziali)
paypalrestsdk.configure({
    "mode": "sandbox",  # Usa "live" in produzione
    "client_id": "AV8r1YLihN5v98tdc6Tloq3tKxJvYikJtSiex4LhCVPzZRO3G7AVE2ZcIsItJhvN-1pPJj6DQ0WOA33N",
    "client_secret": "EHoz2yWbe9HblmXhCG_OjHtHiKBtkzy16rl50QY3epFsPqL8j8LhkZC4_Zh0ffmBqPSH59hxLu6w1cQB"
})

###############################################
# FUNZIONI DI SUPPORTO
###############################################

def init_user_data(chat_id):
    """Inizializza i dati per l'utente se non esistono."""
    if chat_id not in user_data:
        user_data[chat_id] = {
            'services': [],
            'current_service': None,
            'mode': 'normal'
        }

def get_service():
    """Crea e restituisce un servizio Drive autenticato tramite l'account di servizio."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def get_or_create_user_folder(service, username):
    """Cerca (o crea) la cartella su Google Drive per l'utente."""
    query = f"mimeType='application/vnd.google-apps.folder' and name='{username}' and '{FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    if items:
        return items[0]['id']
    else:
        file_metadata = {
            'name': username,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [FOLDER_ID]
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def upload_to_drive(file_path, chat_id):
    """Carica il file su Google Drive nella cartella specifica dell'utente."""
    try:
        service = get_service()
        chat = bot.get_chat(chat_id)
        username = chat.username if chat.username else f"user_{chat_id}"
        user_folder_id = get_or_create_user_folder(service, username)
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [user_folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return "✅ File caricato correttamente"
    except Exception as e:
        return f"⚠️ Errore durante il caricamento: {e}"

def send_service_selection(chat_id):
    """Invia il menu principale per la selezione del servizio."""
    init_user_data(chat_id)
    user_data[chat_id]['mode'] = 'normal'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["📚 Lezioni", "🎙 Podcast", "🎤 Conferenze", "📋 Riepilogo", "❌ Rimuovi un servizio", "✔️ Concludi"]
    markup.add(*buttons)
    bot.send_message(chat_id, "Seleziona il servizio:", reply_markup=markup)

###############################################
# HANDLER DEL BOT
###############################################

@bot.message_handler(commands=['start'])
def welcome(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    send_service_selection(chat_id)

@bot.message_handler(func=lambda message: message.text in ["📚 Lezioni", "🎙 Podcast", "🎤 Conferenze"])
def select_service(message):
    """L'utente sceglie il tipo di servizio."""
    chat_id = message.chat.id
    init_user_data(chat_id)
    user_data[chat_id]['current_service'] = {'name': message.text}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["Economico", "Standard", "Urgente", "🔙 Indietro"]
    markup.add(*buttons)
    bot.send_message(chat_id, "Ora scegli la modalità di consegna:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🔙 Indietro")
def go_back(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    send_service_selection(chat_id)

@bot.message_handler(func=lambda message: message.text in ["Economico", "Standard", "Urgente"])
def select_delivery(message):
    """Permette la scelta della modalità di consegna.
    Se nessun servizio è stato selezionato, non consente di procedere."""
    chat_id = message.chat.id
    init_user_data(chat_id)
    if user_data[chat_id]['current_service'] is None:
        bot.send_message(chat_id, "⚠️ Nessun servizio selezionato. Seleziona un servizio prima.")
        return
    user_data[chat_id]['current_service']['delivery'] = message.text
    bot.send_message(chat_id, "Inserisci la durata in formato HH:MM:SS:")

def format_duration(hours, minutes, seconds):
    parts = []
    if hours > 0:
        parts.append(f"{hours} ore" if hours > 1 else "1 ora")
    if minutes > 0:
        parts.append(f"{minutes} minuti" if minutes > 1 else "1 minuto")
    if seconds > 0:
        parts.append(f"{seconds} secondi" if seconds > 1 else "1 secondo")
    return " ".join(parts) if parts else "0 secondi"

@bot.message_handler(func=lambda message: ':' in message.text)
def insert_duration(message):
    """L'utente inserisce la durata e viene calcolato il prezzo.
    Se non è stato selezionato un servizio, l'operazione viene bloccata."""
    chat_id = message.chat.id
    init_user_data(chat_id)
    if user_data[chat_id]['current_service'] is None:
        bot.send_message(chat_id, "⚠️ Nessun servizio attivo. Seleziona un servizio prima di inserire la durata.")
        return
    try:
        hours, minutes, seconds = map(int, message.text.split(':'))
        duration_text = format_duration(hours, minutes, seconds)
        total_minutes = hours * 60 + minutes + seconds / 60
        total_price = total_minutes * 0.40
        current_service = user_data[chat_id]['current_service']
        current_service['duration'] = duration_text
        current_service['price'] = total_price
        # Attiva l'invio del file
        current_service['file_requested'] = True
        bot.send_message(chat_id, "✅ Durata registrata! Ora invia il file da caricare su Google Drive.")
    except ValueError:
        bot.send_message(chat_id, "⚠️ Formato non valido. Usa HH:MM:SS.")

def process_file(chat_id):
    """Scarica il file inviato dall'utente e lo carica su Google Drive."""
    current = user_data[chat_id]['current_service']
    if current is None or 'file_message' not in current:
        return
    if current.get('multiple_files', False):
        return

    bot.send_message(chat_id, "Il file sta venendo caricato, attendi qualche secondo...")
    file_doc = current['file_message']
    file_path = f"./{file_doc.file_name}"
    file_info = bot.get_file(file_doc.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)
    result = upload_to_drive(file_path, chat_id)
    if result.startswith("✅"):
        current['file'] = file_doc.file_name
        bot.send_message(chat_id, "✅ File caricato correttamente!")
        user_data[chat_id]['services'].append(current)
        user_data[chat_id]['current_service'] = None
        send_service_selection(chat_id)
    else:
        bot.send_message(chat_id, "⚠️ Errore nel caricamento. Riprova inviando il file di nuovo.")
    current.pop('file_message', None)
    current.pop('file_timer', None)
    current.pop('file_requested', None)

@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Gestisce l'invio del file controllando se è richiesto e se non viene inviato più di uno."""
    chat_id = message.chat.id
    init_user_data(chat_id)
    current = user_data[chat_id]['current_service']
    if current is None or not current.get('file_requested', False):
        bot.send_message(chat_id, "⚠️ In questo momento non è richiesto l'invio di un file.")
        return

    if 'file_message' in current:
        if current['file_message'].file_id == message.document.file_id:
            return
        else:
            current['multiple_files'] = True
            if 'file_timer' in current:
                timer = current.pop('file_timer', None)
                if timer:
                    timer.cancel()
            bot.send_message(chat_id, "⚠️ Hai inviato più di un file. Invia un solo file per favore.")
            current.pop('file_message', None)
            return

    current['file_message'] = message.document
    current['multiple_files'] = False
    timer = threading.Timer(3.0, process_file, args=(chat_id,))
    current['file_timer'] = timer
    timer.start()

@bot.message_handler(func=lambda message: message.text == "❌ Rimuovi un servizio")
def remove_service(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    user_data[chat_id]['mode'] = "remove"
    if not user_data[chat_id]['services']:
        bot.send_message(chat_id, "⚠️ Non hai servizi da rimuovere.")
        user_data[chat_id]['mode'] = "normal"
        return
    text = "Scrivi il numero del servizio da rimuovere:\n"
    for idx, service in enumerate(user_data[chat_id]['services']):
        text += f"{idx+1}. {service['name']} - {service['delivery']} ({service['duration']})\n"
    bot.send_message(chat_id, text)

@bot.message_handler(func=lambda message: message.text.isdigit() and user_data.get(message.chat.id, {}).get('mode') == "remove")
def confirm_remove_service(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    idx = int(message.text) - 1
    if 0 <= idx < len(user_data[chat_id]['services']):
        removed_service = user_data[chat_id]['services'].pop(idx)
        bot.send_message(chat_id, f"❌ Servizio rimosso: {removed_service['name']} - {removed_service['delivery']}")
    else:
        bot.send_message(chat_id, "⚠️ Numero non valido.")
    user_data[chat_id]['mode'] = "normal"
    show_summary(message)

@bot.message_handler(func=lambda message: message.text == "📋 Riepilogo")
def show_summary(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    if not user_data[chat_id]['services']:
        bot.send_message(chat_id, "⚠️ Non hai ancora aggiunto servizi.")
        return
    text = "📋 Riepilogo Ordine:\n"
    total_price = sum(s['price'] for s in user_data[chat_id]['services'])
    for idx, service in enumerate(user_data[chat_id]['services']):
        text += f"{idx+1}. {service['name']} - {service['delivery']}\n   ⏳ {service['duration']} → 💰 €{service['price']:.2f}\n"
    text += f"\n💰 Totale: €{total_price:.2f}"
    # Pulsanti per pagare o concludere l'ordine
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💳 Paga con PayPal", "✔️ Concludi")
    bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "✔️ Concludi")
def conclude_order(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    total_price = sum(s['price'] for s in user_data[chat_id]['services'])
    text = "✨ Ordine Concluso!\n📋 Riepilogo Ordine:\n"
    for idx, service in enumerate(user_data[chat_id]['services']):
        text += f"{idx+1}. {service['name']} - {service['delivery']}\n   ⏳ {service['duration']} → 💰 €{service['price']:.2f}\n"
    text += f"\n💰 Totale: €{total_price:.2f}\n🙏 Grazie! Premi /start per un nuovo ordine."
    bot.send_message(chat_id, text, parse_mode='Markdown')
    user_data[chat_id] = {'services': [], 'current_service': None, 'mode': 'normal'}

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
           # MODIFICA QUESTE RIGHE: Sostituisci con il tuo dominio pubblico (ad es. da Render.com)
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
           "description": "Pagamento per i servizi offerti dal bot."
       }]
    })

    if payment.create():
        # Salva il mapping payment_id -> chat_id per l'integrazione PayPal
        orders_mapping[payment.id] = chat_id
        approval_url = None
        for link in payment.links:
            if link.method == "REDIRECT":
                approval_url = str(link.href)
                break
        if approval_url:
            bot.send_message(chat_id, f"Per completare il pagamento, clicca su questo link:\n{approval_url}")
        else:
            bot.send_message(chat_id, "⚠️ Errore: Impossibile ottenere il link di approvazione.")
    else:
        bot.send_message(chat_id, f"⚠️ Errore nella creazione del pagamento: {payment.error}")

if __name__ == '__main__':
    bot.polling(none_stop=True)
