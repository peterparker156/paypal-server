from flask import Flask, request, jsonify
import paypalrestsdk
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Configura il PayPal SDK in modalità live
paypalrestsdk.configure({
    "mode": "live",
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
        logging.debug("Payment trovato: %s", payment.id)
    except Exception as e:
        logging.error("Errore durante il recupero del pagamento: %s", e)
        return f"Errore durante il recupero del pagamento: {e}", 500
    try:
        # Se il pagamento non è già processato, eseguiamo l'execute
        if payment.state not in ["approved", "completed"]:
            if callable(payment.execute):
                if not payment.execute({"payer_id": payer_id}):
                    logging.error("Errore durante l'esecuzione del pagamento: %s", payment.error)
                    error_msg = (payment.error.get("message", str(payment.error))
                                 if isinstance(payment.error, dict) else str(payment.error))
                    return f"Errore durante l'esecuzione del pagamento: {error_msg}", 500
            else:
                logging.debug("payment.execute non callable; assumo pagamento già processato.")
        else:
            logging.debug("Pagamento già processato (stato: %s)", payment.state)
        logging.debug("Pagamento eseguito correttamente")
        custom_field = payment.transactions[0].get("custom")
        if not custom_field:
            logging.debug("Campo custom mancante: pagamento già processato.")
            return '''
            <html>
                <head>
                    <meta charset="utf-8">
                    <title>Pagamento già confermato</title>
                </head>
                <body style="text-align: center; margin-top: 50px;">
                    <h1>Pagamento già confermato!</h1>
                    <p>Il tuo pagamento è già stato processato. Torna al bot per iniziare un nuovo ordine.</p>
                    <a href="https://t.me/AppuntiPerfettiBot" target="_blank">
                        <button style="padding: 10px 20px; font-size: 16px;">Torna al Bot</button>
                    </a>
                </body>
            </html>
            ''', 200
        try:
            chat_id = int(custom_field)
            logging.debug("chat_id recuperato dal campo custom: %s", chat_id)
        except Exception as e:
            logging.error("Errore nel recupero di chat_id dal campo custom: %s", e)
            return f"Errore nel recupero delle informazioni dell'ordine: {e}", 500
        notify_user_payment_success(chat_id)
        return '''
        <html>
            <head>
                <meta charset="utf-8">
                <title>Pagamento Confermato</title>
            </head>
            <body style="text-align: center; margin-top: 50px;">
                <h1>Pagamento confermato!</h1>
                <p>Il tuo pagamento è stato eseguito con successo. L'ordine è andato a buon fine.</p>
                <p>Se il pulsante non funziona, copia questo link: https://t.me/AppuntiPerfettiBot</p>
                <a href="https://t.me/AppuntiPerfettiBot" target="_blank">
                    <button style="padding: 10px 20px; font-size: 16px;">Torna al Bot</button>
                </a>
            </body>
        </html>
        ''', 200
    except Exception as ex:
        logging.error("Eccezione durante l'esecuzione del pagamento: %s", ex)
        return f"Eccezione durante l'esecuzione del pagamento: {ex}", 500

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
            chat_id = int(payment.transactions[0].get("custom"))
            notify_user_payment_success(chat_id)
        except Exception as e:
            logging.error("Errore nel webhook: %s", e)
    return jsonify({'status': 'success'}), 200

from bot import bot, user_data

def notify_user_payment_success(chat_id):
    # Se per qualche motivo il chat_id non è già presente, inizializzalo
    if chat_id not in user_data:
        user_data[chat_id] = {'services': [], 'current_service': None, 'order_id': None, 'mode': 'normal'}
    try:
        logging.debug("Invio notifica di successo a chat_id: %s", chat_id)
        bot.send_message(chat_id, "Il tuo pagamento è stato confermato. L'ordine è andato a buon fine. Grazie per aver acquistato i nostri servizi! Ora puoi iniziare un nuovo ordine.")
        # Resettiamo completamente i dati dell'ordine per questa chat
        user_data[chat_id] = {'services': [], 'current_service': None, 'order_id': None, 'mode': 'normal'}
    except Exception as e:
        logging.error("Errore durante la notifica dell'utente %s: %s", chat_id, e)

@app.route('/')
def home():
    return "Server attivo!"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
