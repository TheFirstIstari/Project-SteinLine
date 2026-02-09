import os
import hashlib
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import psutil
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
        self._emit(self.status_signal, "Initializing Registry Scan...")

        
        
        # 1. Build Incremental Cache
        existing = set()
        try:
            with self.db.get_connection(self.config.registry_db_path) as conn:
                cursor = conn.execute("SELECT path FROM registry")
                existing = {row[0] for row in cursor}
            self._emit(self.status_signal, f"RAM_CACHE_LOADED: {len(existing)} files known.")
        except Exception as e:
            self._emit(self.status_signal, f"CACHE_ERROR: {e}")

        # 2. Discover new files (count only, do not store to avoid memory usage)
        total = 0
        try:
            for root, _, filenames in os.walk(self.config.source_root):
                if not self.is_running:
                    return
                for name in filenames:
                    p = str(Path(root) / name)
                    if p not in existing:
                        total += 1
        except Exception as e:
            self._emit(self.status_signal, f"DISCOVERY_ERROR: {e}")
            return

        self._emit(self.status_signal, f"DISCOVERY_PHASE_COMPLETE: {total} files identified for processing.")
        if total == 0:
            self._emit(self.status_signal, "SYSTEM_IDLE: Registry up to date.")
            self._emit(self.finished_signal, 0)
            return

        self._emit(self.status_signal, f"HASHING_STARTED: {total} new items found.")

        processed = 0
        batch = []

        # 3. Process with Pause/Stop checks using a bounded in-flight task window
        max_in_flight = max(4, self.config.cpu_workers * 2)
        futures = set()
        from concurrent.futures import as_completed, wait, FIRST_COMPLETED

        with ThreadPoolExecutor(max_workers=self.config.cpu_workers) as executor:
            try:
                # Submit tasks as we walk the tree to avoid holding all paths/futures
                for root, _, filenames in os.walk(self.config.source_root):
                    if not self.is_running:
                        break
                    for name in filenames:
                        if not self.is_running:
                            break
                        p = str(Path(root) / name)
                        if p in existing:
                            continue

                        # Submit new hashing task
                        futures.add(executor.submit(self.hash_file, p))

                        # If too many in-flight tasks, wait for some to finish
                        if len(futures) >= max_in_flight:
                            done, _ = wait(futures, return_when=FIRST_COMPLETED)
                            for fut in done:
                                futures.remove(fut)

                                # RAM Safety Check (back-off if over configured limit)
                                while psutil.virtual_memory().used / (1024**3) > self.config.ram_limit_gb:
                                    self._emit(self.status_signal, "MEMORY_CRITICAL: Throttling...")
                                    time.sleep(2)

                                # PAUSE GATE
                                self.mutex.lock()
                                if self.is_paused:
                                    self.pause_cond.wait(self.mutex)
                                self.mutex.unlock()

                                # STOP CHECK
                                if not self.is_running:
                                    break

                                try:
                                    res, path = fut.result()
                                except Exception:
                                    res, path = (None, None)

                                if res:
                                    batch.append((res, path))

                                processed += 1
                                if processed % 50 == 0:
                                    # Update progress and stats periodically
                                    try:
                                        self._emit(self.progress_signal, int((processed/total)*100))
                                        self._emit(self.stats_signal, processed, total)
                                    except Exception:
                                        pass

                                # Commit in blocks to avoid SQLite overhead
                                if len(batch) >= 500:
                                    self._commit(batch)
                                    self._emit(self.status_signal, f"SYNC_PI: Committed block of 500 fingerprints.")
                                    batch = []

                # After submission loop, process remaining futures
                for fut in as_completed(futures):
                    # RAM Safety Check
                    while psutil.virtual_memory().used / (1024**3) > self.config.ram_limit_gb:
                        self._emit(self.status_signal, "MEMORY_CRITICAL: Throttling...")
                        time.sleep(2)

                    # PAUSE GATE
                    self.mutex.lock()
                    if self.is_paused:
                        self.pause_cond.wait(self.mutex)
                    self.mutex.unlock()

                    if not self.is_running:
                        break

                    try:
                        res, path = fut.result()
                    except Exception:
                        res, path = (None, None)

                    if res:
                        batch.append((res, path))

                    processed += 1
                    if processed % 50 == 0:
                        try:
                            self._emit(self.progress_signal, int((processed/total)*100))
                            self._emit(self.stats_signal, processed, total)
                        except Exception:
                            pass

                    if len(batch) >= 500:
                        self._commit(batch)
                        self._emit(self.status_signal, f"SYNC_PI: Committed block of 500 fingerprints.")
                        batch = []

            except Exception as e:
                self._emit(self.status_signal, f"HASHING_ERROR: {e}")
        
        # Final flush
        self._commit(batch)
        self._emit(self.status_signal, f"SCAN_COMPLETE: {processed} files indexed.")
        self._emit(self.finished_signal, processed)

    def _commit(self, batch):
        """Atomic write to the local registry DB."""
        if not batch: return
        try:
            # Use explicit transaction to ensure atomicity and allow rollback on error
            with self.db.get_connection(self.config.registry_db_path) as conn:
                try:
                    conn.execute("BEGIN")
                    conn.executemany("INSERT OR IGNORE INTO registry VALUES (?, ?, 1)", batch)
                    conn.execute("COMMIT")
                except Exception:
                    try:
                        conn.execute("ROLLBACK")
                    except Exception:
                        pass
                    raise
        except Exception as e:
            self._emit(self.status_signal, f"DB_WRITE_ERROR: {e}")

    def _emit(self, signal_obj, *args):
        """Safe emit helper for Qt Signals — falls back to logging/stderr.

        Emitting Qt signals from worker threads can fail if the signal object
        is not in the expected state. Use this helper to avoid raising
        AttributeError and to provide a graceful fallback.
        """
        try:
            signal_obj.emit(*args)
            return
        except Exception:
            try:
                import logging
                logging.warning("Signal emit failed for %s with args %s", getattr(signal_obj, '__name__', str(signal_obj)), args)
            except Exception:
                try:
                    import sys
                    sys.stderr.write(f"Signal emit fallback: {args}\n")
                except Exception:
                    pass