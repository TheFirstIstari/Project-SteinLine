import asyncio
import json
import re
import psutil
import time
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QWaitCondition, QMutex
from .deconstructor import Deconstructor
from ..utils.db_handler import SteinLineDB
from .checkpoint_manager import CheckpointManager
from ..utils.signals import safe_emit
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc

class AnalysisWorker(QThread):
    """The Neural Reasoner thread handling GPU inference and sliding windows."""
    
    # Telemetry Signals
    status_signal = Signal(str)
    stats_signal = Signal(int, int) # (Processed, Facts)
    fact_signal = Signal(list)      # Recent fact rows
    finished_signal = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_running = True
        self.is_paused = False
        self.mutex = QMutex()
        self.pause_cond = QWaitCondition()
        self.db = SteinLineDB(config)
        self.decon = Deconstructor(config)
        self.checkpoint = CheckpointManager(config)
        self.logger = logging.getLogger(__name__)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if not self.is_paused:
            self.pause_cond.wakeAll()

    def stop(self):
        self.is_running = False
        self.is_paused = False
        self.pause_cond.wakeAll()

    def run(self):
        # Heavy imports inside run to keep UI launch fast
        from vllm import LLM, SamplingParams

        try:
            safe_emit(self.status_signal, "Initializing Neural Engine (vLLM)...")
            try:
                llm = LLM(
                    model="Qwen/Qwen2.5-7B-Instruct-AWQ",
                    gpu_memory_utilization=self.config.vram_allocation,
                    max_model_len=self.config.context_window,
                    enforce_eager=True,
                    trust_remote_code=True
                )
            except ValueError as ve:
                # vLLM may raise when requested KV cache exceeds available GPU memory.
                # Retry with a smaller context window to preserve usability.
                safe_emit(self.status_signal, f"LLM_INIT_WARN: {ve}. Retrying with reduced context window.")
                reduced_len = min(self.config.context_window, 8192)
                llm = LLM(
                    model="Qwen/Qwen2.5-7B-Instruct-AWQ",
                    gpu_memory_utilization=max(self.config.vram_allocation, 0.5),
                    max_model_len=reduced_len,
                    enforce_eager=True,
                    trust_remote_code=True
                )

            sampling = SamplingParams(temperature=0, max_tokens=2000, repetition_penalty=1.1)
            
            proc_count = 0
            fact_count = 0

            while self.is_running:
                # PAUSE CHECK
                self.mutex.lock()
                if self.is_paused: 
                    safe_emit(self.status_signal, "ENGINE_PAUSED")
                    self.pause_cond.wait(self.mutex)
                    safe_emit(self.status_signal, "ENGINE_RESUMED")
                self.mutex.unlock()

                # STOP CHECK
                if not self.is_running: break

                batch = self._get_batch()
                if not batch:
                    safe_emit(self.status_signal, "QUEUE_EXHAUSTED: No more files to process.")
                    break

                # Cap number of files processed per cycle to avoid unbounded memory use
                MAX_FILES_PER_CYCLE = getattr(self.config, 'max_files_per_cycle', 64)
                if len(batch) > MAX_FILES_PER_CYCLE:
                    batch = batch[:MAX_FILES_PER_CYCLE]

                prompts = []
                meta = []
                processed_fps = set()

                # Pre-processing / Windowing: extract texts in parallel to maximize CPU utilization
                extractions = []
                with ThreadPoolExecutor(max_workers=max(1, min(self.config.cpu_workers, len(batch)))) as ex:
                    future_map = {ex.submit(self.decon.extract, path): (fp, path) for fp, path in batch}
                    for fut in as_completed(future_map):
                        fp, path = future_map[fut]
                        try:
                            text = fut.result()
                        except Exception:
                            text = None
                        if not text:
                            continue
                        extractions.append((fp, Path(path).name, text))

                # Build prompts and meta from extracted texts
                for fp, fname, text in extractions:
                    # 20k character sliding window
                    chunks = [text[i:i+20000] for i in range(0, len(text), 18000)]
                    for c in chunks:
                        prompts.append(self._build_p(fname, c))
                        meta.append((fp, fname))

                if not prompts:
                    # cleanup and continue
                    try:
                        del extractions
                    except Exception:
                        pass
                    gc.collect()
                    continue

                llm_chunk = int(getattr(self.config, 'llm_chunk_size', 20))
                safe_emit(self.status_signal, f"GPU_REASONING: Processing {len(prompts)} segments in chunks of {llm_chunk}...")

                telemetry_counter = 0
                for start in range(0, len(prompts), llm_chunk):
                    sub_prompts = prompts[start:start+llm_chunk]
                    sub_meta = meta[start:start+llm_chunk]

                    # Adaptive generation: if vLLM raises on large batches, reduce chunk size and retry
                    gen_attempt_chunk = llm_chunk
                    outputs = None
                    while True:
                        try:
                            outputs = llm.generate(sub_prompts, sampling)
                            break
                        except ValueError as ve:
                            # Likely KV cache exhaustion — reduce batch size conservatively
                            safe_emit(self.status_signal, f"LLM_GENERATE_WARN: {ve}. Reducing chunk size from {gen_attempt_chunk}.")
                            gen_attempt_chunk = max(1, gen_attempt_chunk // 2)
                            if gen_attempt_chunk == 1:
                                # give up on this prompt batch; skip to next
                                safe_emit(self.status_signal, "LLM_GENERATE_ERROR: Unable to process chunk; skipping.")
                                outputs = []
                                break
                            # shrink sub_prompts to new size and retry
                            sub_prompts = sub_prompts[:gen_attempt_chunk]
                            sub_meta = sub_meta[:gen_attempt_chunk]
                        except Exception as e:
                            self.logger.exception("Unexpected LLM generate error")
                            outputs = []
                            break

                    results = []
                    for i, out in enumerate(outputs):
                        try:
                            raw = out.outputs[0].text
                        except Exception:
                            continue
                        # Extract objects with regex to ignore chat filler
                        items = re.findall(r'\{[^{}]*\}', raw)
                        for item in items:
                            try:
                                f = json.loads(item.replace('\n',' '))
                                results.append((
                                    sub_meta[i][0], sub_meta[i][1],
                                    str(f.get('source','N/A')),
                                    str(f.get('date','Unknown')),
                                    str(f.get('summary','')),
                                    str(f.get('type','General')),
                                    str(f.get('crime','None')),
                                    1
                                ))
                            except Exception:
                                continue

                    if results:
                        # Save incrementally per chunk to free memory earlier
                        self._save(results)
                        fact_count += len(results)
                        # track which fingerprints produced results so we can mark others as processed
                        try:
                            processed_fps.update([r[0] for r in results])
                        except Exception:
                            pass
                        try:
                            last_fp = results[-1][0] if results else ""
                            self.checkpoint.save_state(proc_count + len(batch), last_fp, fact_count)
                        except Exception:
                            self.logger.exception("Failed to write checkpoint")
                        safe_emit(self.fact_signal, results)

                    # Free references and collect garbage to avoid memory growth
                    try:
                        del outputs
                        del results
                    except Exception:
                        pass
                    gc.collect()

                    # periodic lightweight telemetry
                    telemetry_counter += 1
                    if telemetry_counter % 5 == 0:
                        try:
                            proc = psutil.Process()
                            mem = proc.memory_info().rss
                            vm = psutil.virtual_memory()
                            safe_emit(self.status_signal, f"MEM:RSS={mem//1024//1024}MB VM:{vm.available//1024//1024}MB")
                        except Exception:
                            pass

                # After processing chunks, mark any fingerprints from this batch that produced no results
                try:
                    placeholders = []
                    for fp, path in batch:
                        if fp not in processed_fps:
                            # match expected intelligence table columns: (fingerprint, filename, evidence_quote, associated_date, fact_summary, category, identified_crime, severity_score, timestamp)
                            placeholders.append((fp, Path(path).name, '', '', '', 'General', '', 0, None))
                    if placeholders:
                        # Insert placeholder intelligence rows so files are considered processed
                        self._save(placeholders)
                except Exception:
                    self.logger.exception("Failed to write placeholder intelligence rows")

                # cleanup large buffers
                try:
                    del prompts
                    del meta
                    del extractions
                except Exception:
                    pass
                gc.collect()

                proc_count += len(batch)
                safe_emit(self.stats_signal, proc_count, fact_count)

            safe_emit(self.status_signal, "ENGINE_IDLE: Session Complete.")
            safe_emit(self.finished_signal)
        except Exception as e:
            safe_emit(self.status_signal, f"CRITICAL: {e}")

    def _build_p(self, fn, txt):
        return f"<|im_start|>system\nExtract JSON: source, date, summary, type, crime, severity.<|im_end|>\n<|im_start|>user\nFILE: {fn}\nDATA: {txt}<|im_end|>\n<|im_start|>assistant\n{{\"findings\": ["

    def _get_batch(self):
        try:
            with self.db.get_connection(self.config.registry_db_path) as conn:
                conn.execute(f"ATTACH DATABASE '{self.config.intelligence_db_path}' AS intel")
                # Use LEFT JOIN to avoid large NOT IN subqueries which are slow on big tables
                rows = conn.execute(f"""
                    SELECT r.fingerprint, r.path FROM registry r
                    LEFT JOIN intel.intelligence i ON r.fingerprint = i.fingerprint
                    WHERE i.fingerprint IS NULL
                    LIMIT {self.config.batch_size}
                """).fetchall()

                # Filter out obvious non-content files (sqlite shm/wal, database files, etc.)
                allowed_exts = ('.pdf', '.txt', '.md', '.docx', '.doc', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.mp3', '.wav', '.m4a', '.mp4')
                filtered = []
                for fp, path in rows:
                    p = str(path).lower()
                    # skip sqlite change files and explicitly skip database files
                    if p.endswith('-shm') or p.endswith('-wal') or p.endswith('.db') or '.db-' in p or p.endswith('.sqlite'):
                        continue
                    if any(p.endswith(ext) for ext in allowed_exts):
                        filtered.append((fp, path))
                    # also allow files with no extension but larger than 1KB (likely text)
                    else:
                        try:
                            sp = Path(path)
                            if sp.suffix == '' and sp.exists() and sp.stat().st_size > 1024:
                                filtered.append((fp, path))
                        except Exception:
                            # if path checks fail, skip to be safe
                            continue

                return filtered
        except: return []

    def _save(self, data):
        try:
            # Batch write with explicit checkpointing to keep WAL small and ensure visibility
            with self.db.get_connection(self.config.intelligence_db_path) as conn:
                cur = conn.cursor()
                # Inspect intelligence table to adapt to schema changes
                cur.execute("PRAGMA table_info(intelligence)")
                cols = [r[1] for r in cur.fetchall()]
                # drop 'id' if present (assumed autoincrement)
                insert_cols = [c for c in cols if c != 'id']
                placeholders = ','.join(['?'] * len(insert_cols))
                insert_sql = f"INSERT OR REPLACE INTO intelligence ({','.join(insert_cols)}) VALUES ({placeholders})"

                # Normalize input tuples to match insert_cols length (append None where missing)
                norm = []
                for row in data:
                    r = list(row)
                    if len(r) < len(insert_cols):
                        r.extend([None] * (len(insert_cols) - len(r)))
                    elif len(r) > len(insert_cols):
                        r = r[:len(insert_cols)]
                    norm.append(tuple(r))
                cur.executemany(insert_sql, norm)
                conn.commit()
                try:
                    cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except Exception:
                    # Some sqlite builds may not support pragma or the attach state; ignore
                    pass
        except Exception:
            self.logger.exception("Failed to write intelligence rows")