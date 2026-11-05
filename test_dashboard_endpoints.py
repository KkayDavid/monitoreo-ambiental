"""
Test de verificación de los endpoints de KPIs, Series Temporales y Dashboard Web.
"""

import threading
import time
import requests
import uvicorn
from server.main import app
from edge.storage import EdgeStorage
from edge.collector import SensorCollector
from edge.sync import SyncClient
from etl.etl_hourly import EnvironmentalETL

def iniciar_servidor():
    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.5)
    return server

def test_endpoints():
    server = iniciar_servidor()
    base_url = "http://127.0.0.1:8001"

    print("[1] Verificando endpoint /health...")
    r = requests.get(f"{base_url}/health")
    assert r.status_code == 200, f"Error en health: {r.status_code}"
    print(" -> Health OK")

    print("[2] Verificando endpoint /api/v1/kpis...")
    r = requests.get(f"{base_url}/api/v1/kpis")
    assert r.status_code == 200, f"Error en kpis: {r.status_code}"
    kpis = r.json()
    assert "ambientales" in kpis and "resiliencia_iot" in kpis
    print(f" -> KPIs OK: Riesgo={kpis['ambientales']['riesgo_incendio']}, AQI={kpis['ambientales']['aqi_nivel']}")

    print("[3] Verificando endpoint /api/v1/timeseries...")
    r = requests.get(f"{base_url}/api/v1/timeseries")
    assert r.status_code == 200, f"Error en timeseries: {r.status_code}"
    series = r.json()
    assert "temperatura" in series and "pm25" in series
    print(f" -> Series temporales OK: Muestras temperatura={len(series['temperatura'])}")

    print("[4] Verificando endpoint /api/v1/alerts...")
    r = requests.get(f"{base_url}/api/v1/alerts")
    assert r.status_code == 200, f"Error en alerts: {r.status_code}"
    alertas = r.json()
    print(f" -> Alertas OK: Total alertas registradas={len(alertas)}")

    print("[5] Verificando endpoint /dashboard...")
    r = requests.get(f"{base_url}/dashboard")
    assert r.status_code == 200, f"Error en dashboard: {r.status_code}"
    assert "ETR ZAO" in r.text
    assert "Chart.js" in r.text or "chart-temp-hum" in r.text
    print(" -> Dashboard HTML OK (Renderizado listo para navegador)")

    print("\n TODOS LOS TESTS PASARON EXITOSAMENTE.")

if __name__ == "__main__":
    test_endpoints()
