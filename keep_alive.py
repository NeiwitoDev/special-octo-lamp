"""
Servidor HTTP keep-alive para mantener el bot activo en Render
y permitir que UptimeRobot haga ping periódico.
"""

import os
import logging
import threading
from flask import Flask

log = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/")
def inicio():
    return "✅ V1 Sistemas — Bot activo.", 200


@app.route("/health")
def health():
    return {"status": "ok", "bot": "V1 Sistemas"}, 200


def iniciar_servidor() -> None:
    puerto = int(os.environ.get("PORT", 8080))

    def _run():
        app.run(host="0.0.0.0", port=puerto, debug=False, use_reloader=False)

    hilo = threading.Thread(target=_run, daemon=True, name="keep-alive")
    hilo.start()
    log.info(f"[KEEP-ALIVE] Servidor HTTP iniciado en el puerto {puerto}.")
