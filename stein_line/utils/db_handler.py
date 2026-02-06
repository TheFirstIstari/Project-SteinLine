import sqlite3
import os
from pathlib import Path

class SteinLineDB:
    """Manages forensic databases with configuration-aware locking."""
    
    def __init__(self, config):
        """Initialize using the unified ProjectConfig object."""
        self.config = config
        self.reg_path = config.registry_db_path
        self.intel_path = config.intelligence_db_path
        self._initialize_schema()

    def get_connection(self, db_path: str):
        """Returns a connection optimized for the storage medium (Local vs Pi)."""
        # CIFS/SMB detection
        is_network = "/mnt/" in db_path or db_path.startswith("\\\\")
        
        conn = sqlite3.connect(db_path, timeout=60)
        
        if is_network:
            # Network shares MUST use DELETE mode for stability
            conn.execute("PRAGMA journal_mode=DELETE")
        else:
            # Local SSDs use WAL for maximum speed
            conn.execute("PRAGMA journal_mode=WAL")
            
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

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