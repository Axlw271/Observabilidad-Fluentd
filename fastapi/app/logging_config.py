import logging
import sys
import json
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Formateador personalizado que convierte cada registro de log
    en una línea de texto JSON, en lugar del formato de texto plano
    por defecto de Python. Esto es clave porque Fluentd (y la mayoría
    de los collectors de logs) parsean JSON de forma nativa: cada
    campo queda disponible por separado (timestamp, método, status, etc.)
    en vez de tener que extraerlo con expresiones regulares de una
    línea de texto libre.
    """

    def format(self, record: logging.LogRecord) -> str:
        # record es el objeto que logging.py construye internamente
        # cada vez que llamas a logger.info(...), logger.error(...), etc.
        # Aquí armamos manualmente el diccionario que queremos exportar.
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # extra_fields es un diccionario que nosotros mismos vamos a
        # inyectar en el middleware (lo verás en main.py). Si existe,
        # lo fusionamos al log final. Esto nos permite agregar campos
        # como "method", "path", "status_code", etc. sin modificar
        # este formateador cada vez que queramos un campo nuevo.
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # json.dumps convierte el diccionario de Python a una sola
        # línea de texto JSON válida, que es lo que finalmente se
        # imprime en la consola (y lo que Docker/Fluentd capturarán).
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    """
    Configura y devuelve el logger principal de la aplicación.
    Se llama una sola vez, al arrancar la app (ver main.py).
    """
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    # Le pasamos sys.stdout explícitamente porque logging.StreamHandler(),
    # SIN argumentos, en realidad usa sys.stderr por defecto (un detalle
    # poco intuitivo de la librería estándar de Python). Preferimos stdout
    # porque es la convención estándar para logs de aplicación (stderr
    # se reserva típicamente para errores del framework/proceso). En la
    # práctica no cambia el resultado con Fluentd, ya que el logging
    # driver de Docker captura ambos canales (stdout y stderr) por igual,
    # pero mantenerlo explícito evita confusión al revisar los logs.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    # Evita que se agreguen handlers duplicados si esta función
    # se llegara a invocar más de una vez (por ejemplo con --reload).
    if not logger.handlers:
        logger.addHandler(handler)

    return logger