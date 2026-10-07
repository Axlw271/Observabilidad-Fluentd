from loguru import logger
import sys
import time
import json
from flask import Flask, request

app = Flask(__name__)


def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "security": , #modificar
            "actorOrigin": ,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        return json.dumps(log_entry, ensure_ascii=False)

def serialize(record):
    subset = {
        "timestamp": record["time"].timestamp(),
        "message": record["message"],
        "level": record["level"].name,
        "file": record["file"].name,
        "context": record["extra"],
    }
    return json.dumps(subset)


logger.remove(0)
logger.add(sys.stderr, format="{timestamp}") #Formato del logger
logger.debug("Happy logging with Loguru!")




#MIDDLEWARE

@app.before_request
def log_request():
    print(f"Incoming request: {request.method} {request.url}")

@app.after_request
def log_response(response):
    print(f"Outgoing response: {response.status_code}")
    return response

@app.route('/')
def home():
    return "Hello, Flask!"

if __name__ == '__main__':
    app.run(debug=True)
