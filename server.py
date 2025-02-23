from flask import Flask, request, jsonify
import logging
import paypalrestsdk
from common import save_mapping, get_mapping, notify_user_payment_success

app = Flask(__name__)

@app.route('/', methods=['POST'])
def handle_root_post():
    logging.debug("POST ricevuto: %s", request.get_data())
    return "OK", 200

@app.route('/', methods=['GET'])
def home():
    return "Server attivo!"

@app.route('/payment/execute', methods=['GET'])
def execute_payment():
    payment_id = request.args.get("paymentId")
    payer_id = request.args.get("PayerID")
    logging.debug("Esecuzione pagamento: paymentId=%s, PayerID=%s", payment_id, payer_id)
    if not payment_id or not payer_id:
        return "Errore: Mancano i parametri necessari", 400

    try:
        payment = paypalrestsdk.Payment.find(payment_id)
        payment_dict = payment.to_dict()
        logging.debug("Payment object: %s", payment_dict)
    except Exception as e:
        logging.error("Errore nel recupero del pagamento: %s", e)
        return f"Errore nel recupero del pagamento: {e}", 500

    try:
        success = payment.execute({"payer_id": payer_id})
        if not success:
            logging.error("Errore in execute: %s", payment.error)
            return f"Errore nell'esecuzione del pagamento: {payment.error}", 500
        logging.debug("Pagamento eseguito correttamente")
    except Exception as e:
        logging.error("Eccezione in payment.execute: %s", e)
        return f"Eccezione in esecuzione del pagamento: {e}", 500

    chat_id = None
    try:
        transactions = payment_dict.get("transactions")
        if transactions and len(transactions) > 0:
            custom_value = transactions[0].get("custom")
            logging.debug("Valore custom trovato: %s", custom_value)
            if custom_value:
                chat_id = custom_value
            else:
                chat_id = get_mapping(payment.id)
                if chat_id:
                    logging.debug("chat_id recuperato dal DB: %s", chat_id)
                else:
                    logging.error("Mapping non trovato per payment_id: %s", payment.id)
        else:
            logging.error("Nessuna transazione trovata nel payment object.")
    except Exception as e:
        logging.error("Errore nel recupero di chat_id: %s", e)

    if chat_id:
        notify_user_payment_success(int(chat_id))
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

@app.route('/payment/cancel', methods=['GET'])
def cancel_payment():
    return "Pagamento annullato", 200

@app.route("/webhook", methods=["POST"])
def paypal_webhook():
    event_body = request.get_json()
    if not event_body:
        return jsonify({"error": "No data received"}), 400
    event_type = event_body.get("event_type", "N/D")
    logging.debug("Webhook ricevuto: %s", event_body)
    logging.debug("Tipo evento: %s", event_type)

    if event_type == "PAYMENT.SALE.COMPLETED":
        try:
            payment_id = event_body.get("resource", {}).get("parent_payment")
            if payment_id:
                payment = paypalrestsdk.Payment.find(payment_id)
                payment_dict = payment.to_dict()
                transactions = payment_dict.get("transactions")
                if transactions and len(transactions) > 0:
                    custom_value = transactions[0].get("custom")
                    logging.debug("Webhook SALE COMPLETED, custom: %s", custom_value)
                    chat_id = custom_value if custom_value else get_mapping(payment.id)
                    if chat_id:
                        notify_user_payment_success(int(chat_id))
                    else:
                        logging.error("Mapping non trovato per payment_id: %s", payment_id)
                else:
                    logging.error("Nessuna transazione trovata nel webhook per payment_id: %s", payment_id)
            else:
                logging.error("Parent payment non presente nell'evento SALE COMPLETED")
        except Exception as e:
            logging.error("Errore nel webhook (SALE COMPLETED): %s", e)
    elif event_type == "PAYMENTS.PAYMENT.CREATED":
        logging.info("Evento PAYMENT.CREATED ricevuto. Nessuna azione intrapresa.")
    else:
        logging.info("Evento non gestito: %s", event_type)

    return jsonify({"status": "success"}), 200

@app.route("/webhook/paypal", methods=["POST"])
@app.route("/webhook/paypal/", methods=["POST"])
def paypal_webhook_paypal():
    logging.debug("Webhook /webhook/paypal ricevuto")
    return paypal_webhook()

if __name__ == '__main__':
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
