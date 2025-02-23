from flask import Flask, request, jsonify
import paypalrestsdk
import logging
import os
import psycopg2

logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)

# Leggi la stringa di connessione dal database dalle variabili d'ambiente
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL non è impostato")

# Crea la connessione al database PostgreSQL
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True

# Funzioni per gestire la mapping nel database (chat_id come stringa)
def save_mapping(payment_id, chat_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO payment_mapping (payment_id, chat_id)
            VALUES (%s, %s)
            ON CONFLICT (payment_id)
            DO UPDATE SET chat_id = EXCLUDED.chat_id;
            """,
            (payment_id, chat_id)
        )

def get_mapping(payment_id):
    with conn.cursor() as cur:
        cur.execute("SELECT chat_id FROM payment_mapping WHERE payment_id = %s", (payment_id,))
        result = cur.fetchone()
        return result[0] if result else None

# Configura il PayPal SDK in modalità live
paypalrestsdk.configure({
    "mode": "live",
    "client_id": "ASG04kwKhzR0Bn4s6Bo2N86aRJOwA1hDG3vlHdiJ_i5geeeWLysMiW40_c7At5yOe0z3obNT_4VMkXvi",
    "client_secret": "EMNtcx_GC4M0yGpVKrRKpRmub26OO75BU6oI9hMmc2SQM_z-spPtuH1sZCBme7KCTjhGiEuA-EO21gDg"
})

@app.route('/', methods=['POST'])
def handle_root_post():
    logging.debug("POST received at root: %s", request.get_data())
    return "OK", 200

@app.route('/', methods=['GET'])
def home():
    return "Server attivo!"

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
                    chat_id = custom_value  # trattato come stringa
                else:
                    chat_id = get_mapping(payment.id)
                    if chat_id:
                        logging.debug("Recuperato chat_id dalla mapping DB: %s", chat_id)
                    else:
                        logging.error("Campo custom mancante e mapping non trovato per payment_id: %s", payment.id)
            else:
                logging.error("Nessuna transazione trovata nel payment object.")
        except Exception as e:
            logging.error("Errore nel recupero di chat_id: %s", e)
        if chat_id:
            from bot import notify_user_payment_success  # Importazione ritardata per evitare cicli
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

    event_type = event_body.get('event_type', 'N/D')
    logging.debug("Webhook ricevuto: %s", event_body)
    logging.debug("Tipo evento: %s", event_type)
    
    if event_type == "PAYMENT.SALE.COMPLETED":
        try:
            payment_id = event_body.get('resource', {}).get('parent_payment')
            if payment_id:
                payment = paypalrestsdk.Payment.find(payment_id)
                payment_dict = payment.to_dict()
                transactions = payment_dict.get("transactions")
                if transactions and len(transactions) > 0:
                    custom_value = transactions[0].get("custom")
                    logging.debug("Valore custom nel webhook SALE COMPLETED: %s", custom_value)
                    chat_id = None
                    if custom_value:
                        chat_id = custom_value
                    else:
                        chat_id = get_mapping(payment.id)
                        if chat_id:
                            logging.debug("Recuperato chat_id dalla mapping DB nel webhook: %s", chat_id)
                        else:
                            logging.error("Campo custom mancante e mapping non trovato per payment_id: %s", payment_id)
                    if chat_id:
                        from bot import notify_user_payment_success
                        notify_user_payment_success(chat_id)
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
        
    return jsonify({'status': 'success'}), 200

@app.route('/webhook/paypal', methods=['POST'])
@app.route('/webhook/paypal/', methods=['POST'])
def paypal_webhook_paypal():
    logging.debug("Webhook /webhook/paypal ricevuto")
    return paypal_webhook()

# NOTA: Il blocco di esecuzione diretto è stato rimosso.
