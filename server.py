# server.py
from flask import Flask, request, jsonify
import paypalrestsdk

# Dizionario globale per mappature payment_id -> chat_id
orders_mapping = {}

# Inizializza l'app Flask
app = Flask(__name__)

# Configura il PayPal SDK (usa le tue credenziali)
paypalrestsdk.configure({
    "mode": "sandbox",  # Cambia in "live" in produzione
    "client_id": "AV8r1YLihN5v98tdc6Tloq3tKxJvYikJtSiex4LhCVPzZRO3G7AVE2ZcIsItJhvN-1pPJj6DQ0WOA33N",
    "client_secret": "EHoz2yWbe9HblmXhCG_OjHtHiKBtkzy16rl50QY3epFsPqL8j8LhkZC4_Zh0ffmBqPSH59hxLu6w1cQB"
})

@app.route('/payment/execute', methods=['GET'])
def execute_payment():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    if not payment_id or not payer_id:
        return "Errore: Mancano i parametri necessari", 400

    try:
        payment = paypalrestsdk.Payment.find(payment_id)
    except Exception as e:
        return f"Errore durante il recupero del pagamento: {e}", 500

    if payment.execute({"payer_id": payer_id}):
        chat_id = orders_mapping.get(payment_id)
        if chat_id:
            notify_user_payment_success(chat_id)
        return "Pagamento eseguito con successo!", 200
    else:
        return "Errore durante l'esecuzione del pagamento", 500

@app.route('/payment/cancel', methods=['GET'])
def cancel_payment():
    payment_id = request.args.get('paymentId')
    if payment_id and payment_id in orders_mapping:
        chat_id = orders_mapping[payment_id]
        notify_user_payment_canceled(chat_id)
    return "Pagamento annullato", 200

@app.route('/webhook', methods=['POST'])
def paypal_webhook():
    event_body = request.get_json()
    if not event_body:
        return jsonify({'error': 'No data received'}), 400

    event_type = event_body.get('event_type')
    if event_type == "PAYMENT.SALE.COMPLETED":
        resource = event_body.get('resource', {})
        payment_id = resource.get('parent_payment')
        chat_id = orders_mapping.get(payment_id)
        if chat_id:
            notify_user_payment_success(chat_id)
    return jsonify({'status': 'success'}), 200

# Importa il bot e la struttura dei dati dal file bot.py
from bot import bot, user_data

def notify_user_payment_success(chat_id):
    try:
        bot.send_message(chat_id, "Il tuo pagamento è stato confermato. Grazie per l'acquisto!")
        if chat_id in user_data:
            user_data[chat_id]['services'] = []
            user_data[chat_id]['current_service'] = None
    except Exception as e:
        print(f"Errore durante la notifica dell'utente {chat_id}: {e}")

def notify_user_payment_canceled(chat_id):
    try:
        bot.send_message(chat_id, "Il pagamento è stato annullato. Puoi riprovare quando vuoi.")
    except Exception as e:
        print(f"Errore durante la notifica dell'utente {chat_id}: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
