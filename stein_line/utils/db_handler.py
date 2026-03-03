import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager
from threading import Lock

class SteinLineDB:
    """Manages forensic databases with configuration-aware locking."""
    
    def __init__(self, config):
        """Initialize using the unified ProjectConfig object."""
        self.config = config
        self.reg_path = config.registry_db_path
        self.intel_path = config.intelligence_db_path
        # Simple connection cache for long-running threads
        self._connections = {}
        # Locks per DB path to make connection creation thread-safe
        self._locks = {}
        self._initialize_schema()
    @contextmanager
    def get_connection(self, db_path: str):
        """Context-managed, cached connection factory with a per-path lock.

        Usage:
            with db.get_connection(path) as conn:
                conn.execute(...)
        """
        # Use a fresh connection per call to avoid cross-thread transaction visibility issues.
        is_network = "/mnt/" in db_path or db_path.startswith("\\\\")
        conn = sqlite3.connect(db_path, timeout=60, check_same_thread=False)
        try:
            if is_network:
                conn.execute("PRAGMA journal_mode=DELETE")
            else:
                conn.execute("PRAGMA journal_mode=WAL")

            conn.execute("PRAGMA synchronous=NORMAL")
            try:
                conn.execute("PRAGMA cache_size = -64000")
            except Exception:
                pass

            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _initialize_schema(self):
        """Ensure the forensic tables exist on both storage nodes."""
        # Setup Registry
        with self.get_connection(self.reg_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS registry (
                    fingerprint TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    is_primary INTEGER DEFAULT 1
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fp ON registry(fingerprint)")

        # Setup Intelligence
        with self.get_connection(self.intel_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intelligence (
                    fingerprint TEXT,
                    filename TEXT,
                    evidence_quote TEXT,
                    associated_date TEXT,
                    fact_summary TEXT,
                    category TEXT,
                    identified_crime TEXT,
                    severity_score INTEGER,
                    PRIMARY KEY (fingerprint, filename, evidence_quote)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    fingerprint TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_stage ON processed_files(stage)")

    def mark_processed(self, fingerprint: str, path: str, stage: str):
        with self.get_connection(self.intel_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processed_files (fingerprint, path, stage, processed_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (fingerprint, path, stage),
            )
            conn.commit()

    @staticmethod
    def init_benchmark_schema(db_path: str):
        os.makedirs(Path(db_path).parent, exist_ok=True)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    scenario TEXT NOT NULL,
                    compute_profile TEXT,
                    device_name TEXT,
                    status TEXT NOT NULL,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL,
                    unit TEXT,
                    FOREIGN KEY(run_id) REFERENCES benchmark_runs(run_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bench_metrics_run ON benchmark_metrics(run_id)")
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def benchmark_start(db_path: str, run_id: str, scenario: str, compute_profile: str, device_name: str):
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO benchmark_runs (run_id, started_at, scenario, compute_profile, device_name, status)
                VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, 'running')
                """,
                (run_id, scenario, compute_profile, device_name),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def benchmark_metric(db_path: str, run_id: str, stage: str, metric: str, value: float, unit: str):
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                INSERT INTO benchmark_metrics (run_id, stage, metric, value, unit)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, stage, metric, value, unit),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def benchmark_finish(db_path: str, run_id: str, status: str, notes: str = ""):
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                UPDATE benchmark_runs
                SET completed_at = CURRENT_TIMESTAMP, status = ?, notes = ?
                WHERE run_id = ?
                """,
                (status, notes, run_id),
            )
            conn.commit()
        finally:
            conn.close()