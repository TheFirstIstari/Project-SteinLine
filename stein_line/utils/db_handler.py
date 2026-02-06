import sqlite3
import os
from pathlib import Path

class SteinLineDB:
    """Manages forensic databases with hardware-aware locking protocols."""
    
    def __init__(self, registry_path: str, intelligence_path: str):
        self.reg_path = registry_path
        self.intel_path = intelligence_path
        self._initialize_schema()

    def _get_connection(self, db_path: str):
        """Returns a connection optimized for the storage medium (Local vs Pi)."""
        # CIFS/SMB detection: Network paths often contain /mnt/ or \\
        is_network = "/mnt/" in db_path or db_path.startswith("\\\\")
        
        conn = sqlite3.connect(db_path, timeout=60)
        
        if is_network:
            # Network shares do not support WAL reliably
            conn.execute("PRAGMA journal_mode=DELETE")
        else:
            # Local SSDs perform significantly better with WAL
            conn.execute("PRAGMA journal_mode=WAL")
            
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _initialize_schema(self):
        """Enforce Forensic Data Hierarchy across both nodes."""
        # Registry: Fingerprint (SHA-256) is the Unique Primary Key
        with self._get_connection(self.reg_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS registry (
                    fingerprint TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    is_primary INTEGER DEFAULT 1
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fp ON registry(fingerprint)")

        # Intelligence: Every fact is anchored to a source fingerprint
        with self._get_connection(self.intel_path) as conn:
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

    def fetch_unprocessed(self, limit: int):
        """Retrieve files found in registry but missing from results."""
        # Note: Optimization for large sets involves Python-side diffing
        # to avoid network-intensive ATTACH DATABASE commands.
        with self._get_connection(self.reg_path) as conn:
            cursor = conn.execute(
                "SELECT fingerprint, path FROM registry LIMIT ?", 
                (limit,)
            )
            return cursor.fetchall()