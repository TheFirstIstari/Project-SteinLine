import os
import hashlib
import sqlite3
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QThread, Signal
from ..utils.db_handler import SteinLineDB

class RegistryWorker(QThread):
    # Signals for UI communication
    status_signal = Signal(str)      # Text for console
    progress_signal = Signal(int)    # % for progress bar
    stats_signal = Signal(int, int)  # (Current, Total)
    finished_signal = Signal(int)    # Total new items added

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.db = SteinLineDB(config)
        self.is_running = True

    def hash_file(self, path_str):
        """Worker function for the ThreadPool."""
        try:
            h = hashlib.sha256()
            with open(path_str, "rb") as f:
                while chunk := f.read(1024 * 1024): # 1MB blocks
                    h.update(chunk)
            return (h.hexdigest(), path_str)
        except Exception as e:
            return (None, str(e))

    def run(self):
        start_time = time.time()
        self.status_signal.emit("Initializing Registry Scan...")

        # 1. Load Cache (RAM-speed skip check)
        existing_paths = set()
        try:
            with self.db.get_connection(self.config.registry_db_path) as conn:
                cursor = conn.execute("SELECT path FROM registry")
                existing_paths = {row[0] for row in cursor}
            self.status_signal.emit(f"RAM Cache loaded: {len(existing_paths):,} files known.")
        except Exception as e:
            self.status_signal.emit(f"Cache Error: {e}")

        # 2. Discovery Phase
        self.status_signal.emit(f"Walking directory: {self.config.source_root}")
        new_files = []
        for root, _, filenames in os.walk(self.config.source_root):
            if not self.is_running: return
            for name in filenames:
                full_path = str(Path(root) / name)
                if full_path not in existing_paths:
                    new_files.append(full_path)

        total_new = len(new_files)
        if total_new == 0:
            self.status_signal.emit("Registry up to date. No new files found.")
            self.finished_signal.emit(0)
            return

        self.status_signal.emit(f"Discovered {total_new:,} new items. Starting Hashing...")

        # 3. Parallel Hashing Phase
        processed = 0
        batch = []
        
        with ThreadPoolExecutor(max_workers=self.config.cpu_workers) as executor:
            futures = [executor.submit(self.hash_file, f) for f in new_files]
            
            for future in futures:
                if not self.is_running: break
                
                result, path = future.result()
                if result:
                    batch.append((result, path))
                
                processed += 1
                if processed % 50 == 0: # Update UI every 50 files
                    self.progress_signal.emit(int((processed / total_new) * 100))
                    self.stats_signal.emit(processed, total_new)

                # Batch Commit
                if len(batch) >= 1000:
                    self._commit_batch(batch)
                    batch = []

        self._commit_batch(batch)
        duration = time.time() - start_time
        self.status_signal.emit(f"Registry Process Complete. Time: {duration:.1f}s")
        self.finished_signal.emit(processed)

    def _commit_batch(self, batch):
        if not batch: return
        try:
            with self.db.get_connection(self.config.registry_db_path) as conn:
                conn.executemany("INSERT OR IGNORE INTO registry (fingerprint, path) VALUES (?, ?)", batch)
                conn.commit()
        except Exception as e:
            self.status_signal.emit(f"DB Write Error: {e}")

    def stop(self):
        self.is_running = False