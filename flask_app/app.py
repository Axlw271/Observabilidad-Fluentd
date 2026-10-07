import sys
import time
import json
import logging
from datetime import datetime, timezone

from flask import Flask, request, g

from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

app = Flask(__name__)


class JSONFormatter(logging.Formatter):
    """
    Mismo formateador que usamos en la app de FastAPI: convierte cada
    log en una línea JSON, para que Fluentd la pueda parsear igual de
    bien sin importar de qué framework/lenguaje venga.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        return json.dumps(log_entry, ensure_ascii=False)


logger = logging.getLogger("flask_app")
logger.setLevel(logging.INFO)

# Handler 1 (ya existía): imprime a stdout en JSON -> Docker -> Fluentd.
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(JSONFormatter())

# Handler 2 (nuevo): exporta cada log vía OTLP al Collector.
# "resource" identifica de qué servicio vienen estos logs — sin esto,
# el Collector recibiría los logs sin saber que son de "flask-app"
# (útil para diferenciarlos de los de FastAPI en Jaeger/Prometheus/
# donde sea que termines enviándolos desde el Collector).
resource = Resource.create({"service.name": "flask-app"})
logger_provider = LoggerProvider(resource=resource)
set_logger_provider(logger_provider)

# endpoint="otel-collector:4317" -> el nombre del servicio en
# docker-compose, puerto gRPC que ya expusiste en otel-collector.
# insecure=True porque no configuramos TLS entre contenedores (todo
# corre dentro de la misma red interna de compose).
otlp_exporter = OTLPLogExporter(endpoint="otel-collector:4317", insecure=True)

# BatchLogRecordProcessor agrupa varios logs y los manda juntos cada
# cierto intervalo, en vez de hacer una conexión de red por cada log
# individual (mucho más eficiente bajo carga, como cuando Locust está
# generando tráfico).
logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))

otlp_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

if not logger.handlers:
    logger.addHandler(stdout_handler)
    logger.addHandler(otlp_handler)


# --- Trazas automáticas ---
# Reutilizamos el mismo "resource" de arriba (misma identidad de
# servicio para logs y trazas, así Jaeger/Collector los reconocen
# como el mismo "flask-app").
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)

trace_exporter = OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True)
tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))

# Esta única línea es la que hace la magia: engancha automáticamente
# un "span" (el registro de una traza) a CADA petición que llega a
# esta app Flask, sin que tengamos que crear los spans a mano en cada
# ruta. Incluye método, ruta, código de estado, y tiempo de duración
# — básicamente lo mismo que ya logueamos manualmente, pero ahora
# como una traza real que Jaeger puede visualizar.
FlaskInstrumentor().instrument_app(app)


# Flask no tiene "middleware" con la misma sintaxis que FastAPI, pero
# el equivalente son los hooks before_request/after_request: uno se
# ejecuta ANTES de cada petición, el otro DESPUÉS — juntos nos dejan
# medir cuánto tarda cada request, igual que hicimos con el
# middleware de FastAPI.
@app.before_request
def start_timer():
    # "g" es un objeto especial de Flask para guardar datos que solo
    # viven durante la petición actual (se resetea en cada request).
    g.start_time = time.perf_counter()


@app.after_request
def log_request(response):
    duration_ms = round((time.perf_counter() - g.start_time) * 1000, 2)
    logger.info(
        "request_processed",
        extra={
            "extra_fields": {
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.remote_addr,
            }
        },
    )
    return response


@app.route("/")
def read_root():
    return {"mensaje": "Hola desde Flask!"}


@app.route("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import atexit

    # Sin esto, si el proceso termina abruptamente, el último lote de
    # logs/trazas que los Batch...Processor todavía no habían enviado
    # se perdería (el batching por diseño no envía cada uno al instante).
    atexit.register(logger_provider.shutdown)
    atexit.register(tracer_provider.shutdown)

    # El servidor de desarrollo integrado de Flask (este mismo
    # app.run) no está pensado para producción real, pero para este
    # proyecto de observabilidad es equivalente en espíritu a correr
    # uvicorn directamente sin workers, como ya haces con FastAPI.
    app.run(host="0.0.0.0", port=5000)