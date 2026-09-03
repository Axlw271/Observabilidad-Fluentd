import time
from fastapi import FastAPI, Request

from app.logging_config import setup_logging

app = FastAPI()

# setup_logging() se ejecuta una sola vez, cuando el módulo se importa
# al arrancar uvicorn. logger queda disponible para usarse en cualquier
# parte de este archivo (y podrías importarlo en otros módulos también).
logger = setup_logging()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Un middleware en FastAPI envuelve CADA petición que llega a la app,
    sin importar la ruta. 'call_next' es una función que representa
    "el resto del procesamiento" (o sea: llegar hasta tu endpoint,
    ejecutar su lógica, y regresar la respuesta). Esto nos da un lugar
    central para medir tiempos y loguear, en vez de repetir ese código
    en cada endpoint (/, /health, y los que agregues después).
    """

    # time.perf_counter() es un reloj de alta precisión, ideal para
    # medir duraciones cortas como el tiempo de respuesta de un request.
    start_time = time.perf_counter()

    # Aquí es donde efectivamente se ejecuta tu endpoint (read_root,
    # health_check, etc.). 'response' es el objeto de respuesta que
    # ese endpoint generó.
    response = await call_next(request)

    # Restamos el tiempo final menos el inicial, y lo convertimos
    # a milisegundos multiplicando por 1000 (más legible que segundos
    # para requests que suelen durar unos pocos milisegundos).
    process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # request.client puede ser None en ciertos contextos de prueba,
    # así que usamos una verificación segura antes de acceder a .host.
    client_ip = request.client.host if request.client else "unknown"

    # Aquí es donde usamos el "extra_fields" que definimos en
    # logging_config.py. El diccionario que pasamos en 'extra' se
    # fusiona con el log base dentro de JSONFormatter.format().
    logger.info(
        "request_processed",
        extra={
            "extra_fields": {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": process_time_ms,
                "client_ip": client_ip,
            }
        },
    )

    return response


@app.get("/")
def read_root():
    return {"mensaje": "Hola, mundo2!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}