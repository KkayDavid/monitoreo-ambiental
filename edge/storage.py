import sqlite3
import os
from typing import List, Dict, Any

DB_PATH = os.getenv("EDGE_DB_PATH", "nodo.db")


class EdgeStorage:
    """Almacenamiento local persistente del nodo edge (Store-and-Forward)."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS lectura (
                id          TEXT PRIMARY KEY,
                nodo_id     TEXT NOT NULL,
                sensor      TEXT NOT NULL,
                valor       REAL NOT NULL,
                es_alerta   INTEGER DEFAULT 0,
                ts          TEXT NOT NULL,
                sincronizado INTEGER DEFAULT 0
            );
            """)
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pend
            ON lectura(sincronizado, es_alerta DESC, ts ASC);
            """)
            conn.commit()

    def guardar_lectura(
        self,
        id_: str,
        nodo_id: str,
        sensor: str,
        valor: float,
        ts: str,
        es_alerta: bool = False,
    ):
        """Persiste la lectura de forma inmediata antes de cualquier intento de red."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO lectura
                    (id, nodo_id, sensor, valor, es_alerta, ts, sincronizado)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (id_, nodo_id, sensor, valor, 1 if es_alerta else 0, ts),
            )
            conn.commit()

    def obtener_pendientes(self, lote: int = 100) -> List[Dict[str, Any]]:
        """Devuelve lecturas pendientes ordenadas por prioridad (alertas primero)."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, nodo_id, sensor, valor, es_alerta, ts
                FROM lectura
                WHERE sincronizado = 0
                ORDER BY es_alerta DESC, ts ASC
                LIMIT ?
                """,
                (lote,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def marcar_sincronizados(self, ids: List[str]):
        """Marca como sincronizados los registros confirmados por el servidor."""
        if not ids:
            return
        with self._get_connection() as conn:
            conn.executemany(
                "UPDATE lectura SET sincronizado = 1 WHERE id = ?",
                [(i,) for i in ids],
            )
            conn.commit()

    def conteos(self) -> Dict[str, int]:
        """Estadísticas rápidas del almacén local."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM lectura").fetchone()[0]
            pendientes = conn.execute(
                "SELECT COUNT(*) FROM lectura WHERE sincronizado = 0"
            ).fetchone()[0]
            return {
                "total": total,
                "pendientes": pendientes,
                "sincronizados": total - pendientes,
            }
