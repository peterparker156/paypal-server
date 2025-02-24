import os
import logging
import psycopg2
import paypalrestsdk

logging.basicConfig(level=logging.DEBUG)

# Configurazione del database
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL non è impostato")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True

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

# Leggi le credenziali da variabili d'ambiente se presenti, altrimenti usa valori di default
client_id = os.getenv("PAYPAL_CLIENT_ID", "ASG04kwKhzR0Bn4s6Bo2N86aRJOwA1hDG3vlHdiJ_i5geeeWLysMiW40_c7At5yOe0z3obNT_4VMkXvi")
client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "EMNtcx_GC4M0yGpVKrRKpRmub26OO75BU6oI9hMmc2SQM_z-spPtuH1sZCBme7KCTjhGiEuA-EO21gDg")

paypalrestsdk.configure({
    "mode": os.getenv("PAYPAL_MODE", "live"),  # "live" o "sandbox"
    "client_id": client_id,
    "client_secret": client_secret
})
