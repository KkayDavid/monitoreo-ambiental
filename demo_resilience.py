"""
Prueba de resiliencia Store-and-Forward.

Fases:
  1. Online  : captura y sincronización normal.
  2. Offline : corte de red; el nodo continúa capturando localmente.
  3. Reconexión: vaciado de cola por lotes priorizando alertas.
  4. Idempotencia: re-envío del mismo lote; verificación de cero duplicados.
  5. ETL: agregación horaria.
"""

import os
import threading
import time

import uvicorn

from edge.collector import SensorCollector
from edge.storage import EdgeStorage
from edge.sync import SyncClient
from etl.etl_hourly import EnvironmentalETL
from server.db import CentralDatabase


def _limpiar():
    for f in ("nodo.db", "servidor_central.db"):
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass


def _iniciar_servidor(host: str = "127.0.0.1", port: int = 8000):
    from server.main import app
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    time.sleep(1.5)
    return server


def _banner(titulo: str):
    sep = "=" * 68
    print(f"\n{sep}\n {titulo.upper()}\n{sep}")


def main():
    _banner("Prueba de Resiliencia: Store-and-Forward")
    _limpiar()

    URL_ONLINE  = "http://127.0.0.1:8000/api/v1/sync"
    URL_OFFLINE = "http://127.0.0.1:9999/api/v1/sync"   # puerto cerrado → simula corte

    print("[0] Iniciando servidor central...")
    _iniciar_servidor()
    db_central = CentralDatabase()
    storage    = EdgeStorage()
    collector  = SensorCollector(nodo_id="nodo-demo-01", storage=storage)
    sync       = SyncClient(api_url=URL_ONLINE, storage=storage)

    # --- Fase 1: Online ---
    _banner("Fase 1: Operación normal (conectividad activa)")
    for _ in range(15):
        collector.capturar_lectura()
    s = storage.conteos()
    print(f"-> Nodo: total={s['total']}, pendientes={s['pendientes']}")
    n = sync.sincronizar_todo()
    print(f"-> Sincronizados: {n} | Servidor: {db_central.contar_lecturas()}")

    # --- Fase 2: Offline ---
    _banner("Fase 2: Corte de red (modo offline)")
    sync.api_url = URL_OFFLINE
    for _ in range(35):
        collector.capturar_lectura()
    collector.capturar_lectura(sensor="temperatura", valor=49.5, es_alerta=True)
    collector.capturar_lectura(sensor="pm25",        valor=185.0, es_alerta=True)
    collector.capturar_lectura(sensor="temperatura", valor=52.1,  es_alerta=True)
    s = storage.conteos()
    print(f"-> Nodo offline: total={s['total']}, pendientes={s['pendientes']}")
    intento = sync.sincronizar_lote()
    print(f"-> Enviados durante el corte: {intento} (retenidos en SQLite)")
    print(f"-> Servidor (sin cambios): {db_central.contar_lecturas()}")

    # --- Fase 3: Reconexión ---
    _banner("Fase 3: Reconexión")
    sync.api_url = URL_ONLINE
    n = sync.sincronizar_todo(tamano_lote=25)
    s = storage.conteos()
    total_central = db_central.contar_lecturas()
    print(f"-> Enviados tras reconexión: {n}")
    print(f"-> Nodo: total={s['total']}, pendientes={s['pendientes']}")
    print(f"-> Servidor: {total_central}")

    # --- Fase 4: Idempotencia ---
    _banner("Fase 4: Idempotencia (re-envío por ACK perdido)")
    with storage._get_connection() as conn:
        ultimos = conn.execute(
            "SELECT id, nodo_id, sensor, valor, es_alerta, ts FROM lectura LIMIT 20"
        ).fetchall()
        lote = [dict(r) for r in ultimos]
    db_central.insertar_lote_idempotente(lote)
    post = db_central.contar_lecturas()
    print(f"-> Total tras re-envío: {post}")
    if total_central == post == s["total"]:
        print("[OK] Idempotencia verificada: cero duplicados.")
    else:
        print("[ERROR] Discrepancia detectada.")

    # --- Fase 5: ETL ---
    _banner("Fase 5: ETL – Agregación horaria")
    EnvironmentalETL().ejecutar_pipeline()

    with db_central._get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT sensor, conteo_muestras, valor_promedio, valor_min, valor_max, "
            "alertas_detectadas FROM lectura_hora"
        )
        filas = cur.fetchall()
    encabezado = f"{'Sensor':<14} | {'Muestras':>8} | {'Prom':>8} | {'Min':>8} | {'Max':>8} | {'Alertas':>7}"
    print(f"\n{encabezado}")
    print("-" * len(encabezado))
    for f in filas:
        f = dict(f)
        print(
            f"{f['sensor']:<14} | {f['conteo_muestras']:>8} | "
            f"{f['valor_promedio']:>8} | {f['valor_min']:>8} | "
            f"{f['valor_max']:>8} | {f['alertas_detectadas']:>7}"
        )

    _banner("Prueba finalizada correctamente")


if __name__ == "__main__":
    main()
