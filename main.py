import threading
import sys
from bot import bot
from server import app

def run_flask():
    # Disabilitiamo il reloader per evitare errori sui segnali nel thread secondario
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)

if __name__ == '__main__':
    try:
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.start()
        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        print("Interruzione dell'esecuzione con Ctrl+C. Chiusura in corso...")
        sys.exit(0)
