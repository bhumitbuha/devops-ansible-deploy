from flask import Flask, jsonify
import os
import datetime

app = Flask(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_ENV = os.environ.get("APP_ENV", "dev")

@app.route("/")
def index():
    return jsonify({
        "service": "ps-deployment-toolkit API",
        "version": APP_VERSION,
        "environment": APP_ENV,
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": APP_VERSION}), 200

@app.route("/metrics")
def metrics():
    return jsonify({
        "environment": APP_ENV,
        "uptime_check": "passing",
        "version": APP_VERSION
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=(APP_ENV == "dev"))
