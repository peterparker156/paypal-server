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
        payment_dict = payment.to_dict()
        logging.debug("Payment object: %s", payment_dict)
    except Exception as e:
        logging.error("Errore durante
