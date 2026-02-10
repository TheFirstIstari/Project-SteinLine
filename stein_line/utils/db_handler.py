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