import os
import uvicorn

if __name__ == "__main__":
    port_env = os.environ.get("PORT", "8000")
    try:
        port = int(port_env)
    except ValueError:
        port = 8000

    host = os.environ.get("HOST", "0.0.0.0")
    print(f"[*] Iniciando servidor en {host}:{port}...")
    uvicorn.run("server.main:app", host=host, port=port)
