"""Pruebas de carga para los endpoints de la API con Locust."""

# Locust expone estos nombres dinámicamente; Pylint puede no detectarlos.
# pylint: disable=invalid-name,no-name-in-module
from locust import HttpUser, task, between


class ApiUser(HttpUser):
    """
    Cada instancia de esta clase representa un usuario virtual.
    Locust puede simular cientos de estos en paralelo.

    wait_time define cuánto espera CADA usuario virtual entre una
    tarea y la siguiente — sin esto, Locust dispararía peticiones
    sin pausa, lo cual no simula un patrón de uso realista.
    """
    wait_time = between(1, 3)

    @task(5)
    def get_root(self):
        # El número entre paréntesis en @task es el "peso" relativo
        # de la tarea: con (5) contra (3) y (1) más abajo, esta ruta
        # se ejecutará aproximadamente 5 de cada 9 veces.
        #Esto es un comentario
        self.client.get("/")

    @task(3)
    def get_health(self):
        """Consulta el endpoint de salud de la API."""
        self.client.get("/health")

    @task(1)
    def get_not_found(self):
        # Simula usuarios pidiendo rutas que no existen, para tener
        # variedad de status_code (404) en los logs recolectados.
        # El parámetro "name" agrupa esta ruta en las estadísticas
        # de Locust bajo una sola etiqueta, en vez de una por cada
        # URL distinta que se le ocurra generar.
        self.client.get("/ruta-inexistente", name="/ruta-inexistente [404 esperado]")