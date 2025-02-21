import os
import threading
import time
import telebot
from telebot import types
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import paypalrestsdk  # Per la gestione dei pagamenti

# Configurazione del bot Telegram
API_TOKEN = '7745039187:AAEhlxK64Js4PsnXUlIK7Bbdl5rObgjbFbg'
bot = telebot.TeleBot(API_TOKEN)

# Configurazione di Google Drive
SERVICE_ACCOUNT_FILE = 'appuntiperfetti.json'
SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = "12jHPqbyNEk9itP8MkPpUEDLTMiRj54Jj"

# Dati utente (in memoria)
user_data = {}

###############################################
# CONFIGURAZIONE PAYPAL (modalità live)
###############################################
paypalrestsdk.configure({
    "mode": "live",  # Ambiente live
    "client_id": "ASG04kwKhzR0Bn4s6Bo2N86aRJOwA1hDG3vlHdiJ_i5geeeWLysMiW40_c7At5yOe0z3obNT_4VMkXvi",
    "client_secret": "EMNtcx_GC4M0yGpVKrRKpRmub26OO75BU6oI9hMmc2SQM_z-spPtuH1sZCBme7KCTjhGiEuA-EO21gDg"
})

###############################################
# FUNZIONI DI SUPPORTO
###############################################
def init_user_data(chat_id):
    if chat_id not in user_data:
        user_data[chat_id] = {
            'services': [],
            'current_service': None,
            'mode': 'normal'
        }

def get_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def get_or_create_user_folder(service, username):
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
    init_user_data(chat_id)
    user_data[chat_id]['mode'] = 'normal'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # Tasti standard (senza i tasti di pagamento)
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
# HANDLER DEL BOT (Telegram)
###############################################
@bot.message_handler(commands=['start'])
def welcome(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
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
        "Come funziona:\n"
        "1) Invia il tuo file audio o video\n"
        "2) Ricevi un preventivo personalizzato\n"
        "3) Ottieni la trascrizione pronta all’uso\n"
    )
    bot.send_message(chat_id, pricing_text)
    send_service_selection(chat_id)

@bot.message_handler(func=lambda message: message.text in ["📚 Lezioni", "🎙 Podcast", "🎤 Conferenze"])
def select_service(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    user_data[chat_id]['current_service'] = {'name': message.text}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    if message.text == "📚 Lezioni":
        buttons = ["Economico", "Standard", "Urgente", "🔙 Indietro"]
    else:
        buttons = ["Standard", "Urgente", "🔙 Indietro"]
    markup.add(*buttons)
    bot.send_message(chat_id, "Ora scegli la modalità di consegna:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🔙 Indietro")
def go_back(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    send_service_selection(chat_id)

@bot.message_handler(func=lambda message: message.text in ["Economico", "Standard", "Urgente"])
def select_delivery(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    if user_data[chat_id]['current_service'] is None:
        bot.send_message(chat_id, "⚠️ Nessun servizio selezionato. Seleziona un servizio prima.")
        return
    user_data[chat_id]['current_service']['delivery'] = message.text
    bot.send_message(chat_id, "Inserisci la durata in formato HH:MM:SS:")

@bot.message_handler(func=lambda message: ':' in message.text)
def insert_duration(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    current = user_data[chat_id]['current_service']
    # La durata può essere inserita solo se la modalità di consegna è stata scelta
    if current is None or "delivery" not in current:
        bot.send_message(chat_id, "⚠️ Non è richiesta l'inserimento della durata in questo momento.")
        return
    try:
        hours, minutes, seconds = map(int, message.text.split(':'))
        duration_text = format_duration(hours, minutes, seconds)
        total_minutes = hours * 60 + minutes + seconds / 60
        price_per_min = compute_price(current['name'], current['delivery'], total_minutes)
        total_price = total_minutes * price_per_min
        current['duration'] = duration_text
        current['price'] = total_price
        current['file_requested'] = True
        bot.send_message(chat_id, f"✅ Durata registrata! Totale: €{total_price:.2f}\nOra invia il file da caricare su Google Drive.")
    except ValueError:
        bot.send_message(chat_id, "⚠️ Formato non valido. Usa HH:MM:SS.")

def process_file(chat_id):
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
        # Resettiamo l'ordine e inviamo la conferma
        user_data[chat_id]['current_service'] = None
        bot.send_message(chat_id, "L'ordine è stato completato. Ora puoi iniziare un nuovo ordine.")
        send_service_selection(chat_id)
    else:
        bot.send_message(chat_id, "⚠️ Errore nel caricamento. Riprova inviando il file di nuovo.")
    current.pop('file_message', None)
    current.pop('file_timer', None)
    current.pop('file_requested', None)

@bot.message_handler(content_types=['document'])
def handle_document(message):
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
        delivery = service.get('delivery', 'N/A')
        text += f"{idx+1}. {service['name']} - {delivery} ({service.get('duration','N/A')})\n"
    bot.send_message(chat_id, text)

@bot.message_handler(func=lambda message: message.text.isdigit() and user_data.get(message.chat.id, {}).get('mode') == "remove")
def confirm_remove_service(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    idx = int(message.text) - 1
    if 0 <= idx < len(user_data[chat_id]['services']):
        removed_service = user_data[chat_id]['services'].pop(idx)
        bot.send_message(chat_id, f"❌ Servizio rimosso: {removed_service['name']} - {removed_service.get('delivery', 'N/A')}")
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
        text += f"{idx+1}. {service['name']} - {service.get('delivery','N/A')}\n   ⏳ {service.get('duration','N/A')} → 💰 €{service['price']:.2f}\n"
    text += f"\n💰 Totale: €{total_price:.2f}"
    # Mostra i tasti standard (non includono i tasti per il pagamento)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 Lezioni", "🎙 Podcast", "🎤 Conferenze", "📋 Riepilogo", "❌ Rimuovi un servizio", "✔️ Concludi")
    bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "✔️ Concludi")
def conclude_order(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    total_price = sum(s['price'] for s in user_data[chat_id]['services'])
    if total_price == 0:
        bot.send_message(chat_id, "⚠️ Nessun servizio selezionato per il pagamento.")
        send_service_selection(chat_id)
        return
    text = "✨ Ordine Concluso!\n📋 Riepilogo Ordine:\n"
    for idx, service in enumerate(user_data[chat_id]['services']):
        text += f"{idx+1}. {service['name']} - {service.get('delivery','N/A')}\n   ⏳ {service.get('duration','N/A')} → 💰 €{service['price']:.2f}\n"
    text += f"\n💰 Totale: €{total_price:.2f}\n\nSe vuoi procedere con il pagamento, clicca su '💳 Paga con PayPal'."
    # Solo in questo handler mostriamo i tasti "💳 Paga con PayPal" e "❌ Annulla Ordine"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💳 Paga con PayPal", "❌ Annulla Ordine")
    bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "❌ Annulla Ordine")
def cancel_order(message):
    chat_id = message.chat.id
    init_user_data(chat_id)
    user_data[chat_id] = {'services': [], 'current_service': None, 'mode': 'normal'}
    bot.send_message(chat_id, "❌ Ordine annullato e resettato. Premi /start per iniziare un nuovo ordine.")

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

    print("Creazione pagamento...")
    if payment.create():
        print("Pagamento creato, payment.id =", payment.id)
        approval_url = None
        for link in payment.links:
            print("Link trovato:", link.rel, link.href)
            if link.rel == "approval_url":
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
