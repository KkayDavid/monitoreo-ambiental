import uuid
import random
from datetime import datetime, timezone
from edge.storage import EdgeStorage


class SensorCollector:
    """
    Captura lecturas de sensores ambientales y las persiste localmente.

    En producción, sustituir el generador aleatorio por la lectura real
    del sensor físico (BME280, PMS5003, SCD30, etc.) mediante I2C/UART.
    """

    # Rangos de operación normales y umbrales de alerta para clima tropical
    _RANGOS = {
        "temperatura": (23.0, 34.0, 46.0, 55.0, 45.0),   # (min_norm, max_norm, min_alerta, max_alerta, umbral)
        "humedad":     (70.0, 98.0, None, None, None),
        "pm25":        (5.0, 25.0, 105.0, 250.0, 100.0),
        "co2":         (400.0, 550.0, None, None, None),
    }

    def __init__(self, nodo_id: str = "nodo-01", storage: EdgeStorage = None):
        self.nodo_id = nodo_id
        self.storage = storage or EdgeStorage()

    def capturar_lectura(
        self,
        sensor: str = None,
        valor: float = None,
        es_alerta: bool = False,
    ) -> dict:
        """Genera o recibe una lectura y la almacena de forma durable antes de enviarla."""
        sensores_disponibles = list(self._RANGOS.keys())
        sensor = sensor or random.choice(sensores_disponibles)

        if valor is None:
            rango = self._RANGOS.get(sensor, (0.0, 100.0, None, None, None))
            if es_alerta and rango[2] is not None:
                valor = round(random.uniform(rango[2], rango[3]), 2)
            else:
                valor = round(random.uniform(rango[0], rango[1]), 2)

        lectura_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()

        self.storage.guardar_lectura(
            id_=lectura_id,
            nodo_id=self.nodo_id,
            sensor=sensor,
            valor=valor,
            ts=ts,
            es_alerta=es_alerta,
        )

        return {
            "id": lectura_id,
            "nodo_id": self.nodo_id,
            "sensor": sensor,
            "valor": valor,
            "es_alerta": es_alerta,
            "ts": ts,
        }
