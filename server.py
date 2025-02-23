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
                    chat_id = custom_value  # salvato come stringa
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
            # Convertiamo il chat_id in intero prima di passarlo, così corrisponde alla chiave in user_data
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
    else:
        logging.error("Errore durante l'esecuzione del pagamento: %s", payment.error)
        return f"Errore durante l'esecuzione del pagamento: {payment.error}", 500

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
                        # Convertiamo il chat_id in intero per garantire la corrispondenza con user_data
                        notify_user_payment_success(int(chat_id))
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

