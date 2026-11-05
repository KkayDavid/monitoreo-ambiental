"""
Test de verificación del importador de ThingSpeak JSON.
"""

import time
import json
import threading
import requests
import uvicorn
from server.main import app

def iniciar_servidor_test(port=8002):
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.5)
    return server

def test_thingspeak():
    iniciar_servidor_test()
    base_url = "http://127.0.0.1:8002"

    with open("thingspeak_ejemplo.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

    print("[1] Enviando JSON de ThingSpeak al endpoint /api/v1/import/thingspeak...")
    r = requests.post(f"{base_url}/api/v1/import/thingspeak", json=payload)
    assert r.status_code == 200, f"Error {r.status_code}: {r.text}"
    data = r.json()
    print(" -> Respuesta exitosa:", data["mensaje"])
    print(f" -> Lecturas generadas: {data['lecturas_generadas']}, Alertas: {data['alertas_detectadas']}")
    total_inicial = data["total_en_servidor"]

    print("[2] Prueba de Idempotencia: reenviando exactamente el mismo JSON...")
    r2 = requests.post(f"{base_url}/api/v1/import/thingspeak", json=payload)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["total_en_servidor"] == total_inicial, "Error: ¡Se crearon duplicados!"
    print(f" -> Idempotencia perfecta: El total en servidor se mantiene en {data2['total_en_servidor']} registros.")

    print("[3] Verificando que las alertas de ThingSpeak aparecen en /api/v1/alerts...")
    r_alerts = requests.get(f"{base_url}/api/v1/alerts")
    alertas = r_alerts.json()
    assert len(alertas) > 0, "No se registraron alertas"
    print(f" -> Alertas verificadas: {len(alertas)} alertas registradas.")

    print("[4] Verificando KPIs actualizados...")
    r_kpis = requests.get(f"{base_url}/api/v1/kpis")
    kpis = r_kpis.json()
    print(f" -> KPIs Ambientales: Riesgo={kpis['ambientales']['riesgo_incendio']}, Temp Max={kpis['ambientales']['temperatura_max']}°C")

    print("\n TODOS LOS TESTS DE THINGSPEAK PASARON EXITOSAMENTE.")

if __name__ == "__main__":
    test_thingspeak()
