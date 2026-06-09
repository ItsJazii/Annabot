"""Flask health check endpoints for Render."""

from flask import Flask

from anna.core.config import PORT

app = Flask(__name__)


@app.route("/")
def health():
    return "Anna is running!"


@app.route("/health")
def health_check():
    return {"status": "ok"}


def run_health_server():
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=PORT)
    except ImportError:
        app.run(host="0.0.0.0", port=PORT)
