import gzip
import json
import logging
import requests
from edge.storage import EdgeStorage

logger = logging.getLogger(__name__)


class SyncClient:
    """
    Cliente de sincronización Store-and-Forward.

    Envía lotes comprimidos de lecturas al servidor central.
    Cuando no hay conectividad, los datos permanecen en SQLite local
    y se reintentan en el siguiente ciclo sin pérdida de información.
    """

    def __init__(
        self,
        api_url: str,
        storage: EdgeStorage = None,
        timeout: int = 10,
        comprimir: bool = True,
    ):
        self.api_url = api_url
        self.storage = storage or EdgeStorage()
        self.timeout = timeout
        self.comprimir = comprimir

    def sincronizar_lote(self, tamano_lote: int = 100) -> int:
        """
        Intenta enviar un lote de lecturas pendientes.
        Retorna el número de registros confirmados (0 si falla o no hay datos).
        """
        pendientes = self.storage.obtener_pendientes(tamano_lote)
        if not pendientes:
            return 0

        payload_bytes = json.dumps(pendientes).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        if self.comprimir:
            headers["Content-Encoding"] = "gzip"
            data = gzip.compress(payload_bytes)
        else:
            data = payload_bytes

        try:
            response = requests.post(
                self.api_url,
                data=data,
                headers=headers,
                timeout=self.timeout,
            )
            if response.status_code in (200, 201):
                ids_confirmados = [p["id"] for p in pendientes]
                self.storage.marcar_sincronizados(ids_confirmados)
                logger.info("Sincronizados %d registros.", len(ids_confirmados))
                return len(ids_confirmados)
            else:
                logger.warning(
                    "Respuesta inesperada del servidor: %s", response.status_code
                )
                return 0
        except requests.RequestException:
            logger.info(
                "Sin conectividad hacia %s. Se reintentará en el próximo ciclo.",
                self.api_url,
            )
            return 0

    def sincronizar_todo(self, tamano_lote: int = 100) -> int:
        """Drena la cola local enviando lotes sucesivos hasta vaciarla o perder red."""
        total = 0
        while True:
            enviados = self.sincronizar_lote(tamano_lote)
            if enviados == 0:
                break
            total += enviados
        return total
