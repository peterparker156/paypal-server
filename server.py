from flask import Flask, request, jsonify
import paypalrestsdk
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Configura il PayPal SDK in modalità live
paypalrestsdk.configure({
    "mode": "live",  # Ambiente live
    "client_id": "ASG04kwKhzR0Bn4s6Bo2N86aRJOwA1hDG3vlHdiJ_i5geeeWLysMiW40_c7At5yOe0z3obNT_4VMkXvi",
    "client_secret": "EMNtcx_GC4M0yGpVKrRKpRmub26OO75BU6oI9hMmc2SQM_z-spPtuH1sZCBme7KCTjhGiEuA-EO21gDg"
})

@app.route('/payment/execute', methods=['GET'])
def execute_payment():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    logging.debug("Esecuzione pagamento: paymentId=%s, PayerID=%s", payment_id, payer_id)
    if not payment_id or not payer_id:
        return "Errore: Mancano i parametri necessari", 400

    try:
        payment = paypalrestsdk.Payment.find(payment_id)
        payment_dict = payment.to_dict()
        logging.debug("Payment object: %s", payment_dict)
    except Exception as e:
        logging.error("Errore durante il recupero del pagamento: %s", e)
        return f"Errore durante il recupero del pagamento: {e}", 500

    if payment.execute({"payer_id": payer_id}):
        logging.debug("Pagamento eseguito correttamente")
        chat_id = None
        try:
            transactions = payment_dict.get("transactions")
            if transactions and len(transactions) > 0:
                custom_value = transactions[0].get("custom")
                logging.debug("Valore custom trovato: %s", custom_value)
                if custom_value:
                    chat_id = int(custom_value)
                else:
                    logging.error("Campo custom mancante nella transazione.")
            else:
                logging.error("Nessuna transazione trovata nel payment object.")
        except Exception as e:
            logging.error("Errore nel recupero di chat_id dal campo custom: %s", e)
        if chat_id:
            notify_user_payment_success(chat_id)
        else:
            logging.warning("Nessun chat_id trovato per payment_id: %s", payment_id)
        return '''
        <html>
            <head>
                <meta charset="utf-8">
                <title>Pagamento Confermato</title>
            </head>
            <body style="text-align: center; margin-top: 50px;">
                <h1>Pagamento confermato!</h1>
                <p>Il tuo pagamento è stato eseguito con successo. L'ordine è andato a buon fine.</p>
                <a href="https://t.me/AppuntiPerfettiBot" target="_blank">
                    <button style="padding: 10px 20px; font-size: 16px;">Torna al Bot</button>
                </a>
            </body>
        </html>
        ''', 200
    else:
        logging.error("Errore durante l'esecuzione del pagamento: %s", payment.error)
        return f"Errore durante l'esecuzione del pagamento: {payment.error}", 500

@app.route('/payment/cancel', methods=['GET'])
def cancel_payment():
    return "Pagamento annullato", 200

@app.route('/webhook', methods=['POST'])
def paypal_webhook():
    event_body = request.get_json()
    if not event_body:
        return jsonify({'error': 'No data received'}), 400

    event_type = event_body.get('event_type')
    logging.debug("Webhook ricevuto: event_type=%s", event_type)
    if event_type == "PAYMENT.SALE.COMPLETED":
        resource = event_body.get('resource', {})
        payment_id = resource.get('parent_payment')
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            payment_dict = payment.to_dict()
            transactions = payment_dict.get("transactions")
            if transactions and len(transactions) > 0:
                custom_value = transactions[0].get("custom")
                if custom_value:
                    chat_id = int(custom_value)
                    notify_user_payment_success(chat_id)
                else:
                    logging.error("Campo custom mancante nel webhook per payment_id: %s", payment_id)
            else:
                logging.error("Nessuna transazione trovata nel webhook per payment_id: %s", payment_id)
        except Exception as e:
            logging.error("Errore nel webhook: %s", e)
    return jsonify({'status': 'success'}), 200

# Route per webhook a /webhook/paypal (con e senza trailing slash)
@app.route('/webhook/paypal', methods=['POST'])
@app.route('/webhook/paypal/', methods=['POST'])
def paypal_webhook_paypal():
    logging.debug("Webhook /webhook/paypal ricevuto")
    return paypal_webhook()

# Importa il bot e i dati dal file bot.py
from bot import bot, user_data

def notify_user_payment_success(chat_id):
    try:
        logging.debug("Invio notifica di successo a chat_id: %s", chat_id)
        bot.send_message(chat_id, "Il tuo pagamento è stato confermato. L'ordine è andato a buon fine. Grazie per aver acquistato i nostri servizi!")
        # Reset completo dei dati dell'ordine per il chat_id
        user_data[chat_id] = {'services': [], 'current_service': None, 'mode': 'normal'}
    except Exception as e:
        logging.error("Errore durante la notifica dell'utente %s: %s", chat_id, e)

@app.route('/')
def home():
    return "Server attivo!"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
