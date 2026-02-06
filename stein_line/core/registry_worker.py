import os
import hashlib
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
# IMPORT FIX: Added QMutex and QWaitCondition
from PySide6.QtCore import QThread, Signal, QWaitCondition, QMutex 
from ..utils.db_handler import SteinLineDB

class RegistryWorker(QThread):
    """Parallel hashing worker with pause/resume capability."""
    
    status_signal = Signal(str)
    progress_signal = Signal(int)
    stats_signal = Signal(int, int)
    finished_signal = Signal(int)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.db = SteinLineDB(config)
        self.is_running = True
        self.is_paused = False
        
        # Synchronization primitives for pause/resume
        self.mutex = QMutex()
        self.pause_cond = QWaitCondition()

    def toggle_pause(self):
        """Thread-safe toggle for the pause state."""
        self.is_paused = not self.is_paused
        if not self.is_paused:
            self.pause_cond.wakeAll()

    def stop(self):
        """Gracefully halt the worker."""
        self.is_running = False
        self.is_paused = False
        self.pause_cond.wakeAll()

    def hash_file(self, path_str):
        """Standard SHA-256 block hashing."""
        try:
            h = hashlib.sha256()
            with open(path_str, "rb") as f:
                while chunk := f.read(1024 * 1024): # 1MB chunks
                    h.update(chunk)
            return (h.hexdigest(), path_str)
        except:
            return (None, path_str)

    def run(self):
        self.status_signal.emit("Initializing Registry Scan...")

        for future in futures:
                # NEW: RAM Safety Check
                while psutil.virtual_memory().used / (1024**3) > self.config.ram_limit_gb:
                    self.status_signal.emit("MEMORY_CRITICAL: Throttling...")
                    time.sleep(2) # Back-off
        
        # 1. Build Incremental Cache
        existing = set()
        try:
            with self.db.get_connection(self.config.registry_db_path) as conn:
                cursor = conn.execute("SELECT path FROM registry")
                existing = {row[0] for row in cursor}
            self.status_signal.emit(f"RAM_CACHE_LOADED: {len(existing)} files known.")
        except Exception as e:
            self.status_signal.emit(f"CACHE_ERROR: {e}")

        # 2. Discover new files
        new_files = []
        for root, _, filenames in os.walk(self.config.source_root):
            if not self.is_running: return
            for name in filenames:
                p = str(Path(root) / name)
                if p not in existing: 
                    new_files.append(p)
        self.status_signal.emit(f"DISCOVERY_PHASE_COMPLETE: {total} files identified for processing.")
        total = len(new_files)
        if total == 0:
            self.status_signal.emit("SYSTEM_IDLE: Registry up to date.")
            self.finished_signal.emit(0)
            return

        self.status_signal.emit(f"HASHING_STARTED: {total} new items found.")

        processed = 0
        batch = []

        # 3. Process with Pause/Stop checks
        with ThreadPoolExecutor(max_workers=self.config.cpu_workers) as executor:
            futures = [executor.submit(self.hash_file, f) for f in new_files]
            for future in futures:
                if len(batch) >= 500:
                    self._commit(batch)
                    self.status_signal.emit(f"SYNC_PI: Committed block of 500 fingerprints.")
                    batch = []
                # PAUSE GATE
                self.mutex.lock()
                if self.is_paused:
                    self.pause_cond.wait(self.mutex)
                self.mutex.unlock()

                # STOP CHECK
                if not self.is_running: return

                res, path = future.result()
                if res: 
                    batch.append((res, path))
                
                processed += 1
                if processed % 50 == 0:
                    self.progress_signal.emit(int((processed/total)*100))
                    self.stats_signal.emit(processed, total)
                
                # Commit in blocks to avoid SQLite overhead
                if len(batch) >= 500:
                    self._commit(batch)
                    batch = []
        
        # Final flush
        self._commit(batch)
        self.status_signal.emit(f"SCAN_COMPLETE: {processed} files indexed.")
        self.finished_signal.emit(processed)

    def _commit(self, batch):
        """Atomic write to the local registry DB."""
        if not batch: return
        try:
            with self.db.get_connection(self.config.registry_db_path) as conn:
                conn.executemany("INSERT OR IGNORE INTO registry VALUES (?, ?, 1)", batch)
                conn.commit()
        except Exception as e:
            self.status_signal.emit(f"DB_WRITE_ERROR: {e}")