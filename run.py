"""
Demo ADIRA - Couche Semantique & IA
Usage: python run.py
"""
import webbrowser
import time
import threading

import uvicorn


def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    print("Demarrage du serveur sur http://localhost:5000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)
