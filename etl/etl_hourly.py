import os
import sqlite3

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///servidor_central.db")


class EnvironmentalETL:
    """
    Pipeline ETL de agregación horaria.

    Extracción : lecturas crudas de la tabla `lectura`.
    Transformación: filtrado de valores fuera de rango físico y cálculo de
                    estadísticos por ventana de una hora.
    Carga       : upsert en la tabla `lectura_hora`, lista para visualización.
    """

    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url
        self.is_sqlite = db_url.startswith("sqlite")
        self._init_target_table()

    def _get_connection(self):
        if self.is_sqlite:
            path = self.db_url.replace("sqlite:///", "")
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return conn
        import psycopg2
        return psycopg2.connect(self.db_url)

    def _init_target_table(self):
        with self._get_connection() as conn:
            conn.cursor().execute("""
            CREATE TABLE IF NOT EXISTS lectura_hora (
                hora_utc            TEXT NOT NULL,
                nodo_id             TEXT NOT NULL,
                sensor              TEXT NOT NULL,
                conteo_muestras     INTEGER NOT NULL,
                valor_promedio      REAL NOT NULL,
                valor_min           REAL NOT NULL,
                valor_max           REAL NOT NULL,
                alertas_detectadas  INTEGER NOT NULL,
                PRIMARY KEY (hora_utc, nodo_id, sensor)
            );
            """)
            conn.commit()

    def ejecutar_pipeline(self):
        """Agrega lecturas por hora y actualiza la tabla de resumen."""
        with self._get_connection() as conn:
            cur = conn.cursor()

            if self.is_sqlite:
                select_q = """
                SELECT
                    substr(ts, 1, 13) || ':00:00' AS hora_utc,
                    nodo_id,
                    sensor,
                    COUNT(*)        AS conteo_muestras,
                    ROUND(AVG(valor), 2) AS valor_promedio,
                    MIN(valor)      AS valor_min,
                    MAX(valor)      AS valor_max,
                    SUM(es_alerta)  AS alertas_detectadas
                FROM lectura
                WHERE
                    (sensor = 'temperatura' AND valor BETWEEN 10.0 AND 60.0) OR
                    (sensor = 'humedad'     AND valor BETWEEN 20.0 AND 100.0) OR
                    (sensor = 'pm25'        AND valor BETWEEN 0.0  AND 500.0) OR
                    (sensor = 'co2'         AND valor BETWEEN 200.0 AND 2000.0)
                GROUP BY hora_utc, nodo_id, sensor
                """
                upsert_q = """
                INSERT INTO lectura_hora
                    (hora_utc, nodo_id, sensor, conteo_muestras,
                     valor_promedio, valor_min, valor_max, alertas_detectadas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (hora_utc, nodo_id, sensor) DO UPDATE SET
                    conteo_muestras    = excluded.conteo_muestras,
                    valor_promedio     = excluded.valor_promedio,
                    valor_min          = excluded.valor_min,
                    valor_max          = excluded.valor_max,
                    alertas_detectadas = excluded.alertas_detectadas;
                """
            else:
                select_q = """
                SELECT
                    to_char(date_trunc('hour', ts::timestamp),
                            'YYYY-MM-DD HH24:MI:SS') AS hora_utc,
                    nodo_id,
                    sensor,
                    COUNT(*)                AS conteo_muestras,
                    ROUND(AVG(valor)::numeric, 2) AS valor_promedio,
                    MIN(valor)              AS valor_min,
                    MAX(valor)              AS valor_max,
                    SUM(es_alerta)          AS alertas_detectadas
                FROM lectura
                WHERE
                    (sensor = 'temperatura' AND valor BETWEEN 10.0 AND 60.0) OR
                    (sensor = 'humedad'     AND valor BETWEEN 20.0 AND 100.0) OR
                    (sensor = 'pm25'        AND valor BETWEEN 0.0  AND 500.0) OR
                    (sensor = 'co2'         AND valor BETWEEN 200.0 AND 2000.0)
                GROUP BY hora_utc, nodo_id, sensor
                """
                upsert_q = """
                INSERT INTO lectura_hora
                    (hora_utc, nodo_id, sensor, conteo_muestras,
                     valor_promedio, valor_min, valor_max, alertas_detectadas)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (hora_utc, nodo_id, sensor) DO UPDATE SET
                    conteo_muestras    = EXCLUDED.conteo_muestras,
                    valor_promedio     = EXCLUDED.valor_promedio,
                    valor_min          = EXCLUDED.valor_min,
                    valor_max          = EXCLUDED.valor_max,
                    alertas_detectadas = EXCLUDED.alertas_detectadas;
                """

            cur.execute(select_q)
            filas = cur.fetchall()
            for f in filas:
                if self.is_sqlite:
                    cur.execute(upsert_q, (
                        f["hora_utc"], f["nodo_id"], f["sensor"],
                        f["conteo_muestras"], f["valor_promedio"],
                        f["valor_min"], f["valor_max"], f["alertas_detectadas"],
                    ))
                else:
                    cur.execute(upsert_q, tuple(f))

            conn.commit()
            print(f"[ETL] {len(filas)} ventanas horarias procesadas.")


if __name__ == "__main__":
    EnvironmentalETL().ejecutar_pipeline()
