@echo off
echo ===================================================
echo  Iniciando Tablero ETR ZAO - Amazonia (PlanetAI / UNAD)
echo ===================================================
echo  Abriendo servidor en http://localhost:8000/dashboard
echo  Presiona Ctrl + C para detener.
echo ===================================================
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
