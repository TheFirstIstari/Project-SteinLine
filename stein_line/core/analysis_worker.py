import asyncio
import json
import re
import psutil
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QWaitCondition, QMutex
from .deconstructor import Deconstructor
from ..utils.db_handler import SteinLineDB

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
            self.status_signal.emit("Initializing Neural Engine (vLLM)...")
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
                self.status_signal.emit(f"LLM_INIT_WARN: {ve}. Retrying with reduced context window.")
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
                    self.status_signal.emit("ENGINE_PAUSED")
                    self.pause_cond.wait(self.mutex)
                    self.status_signal.emit("ENGINE_RESUMED")
                self.mutex.unlock()

                # STOP CHECK
                if not self.is_running: break

                batch = self._get_batch()
                if not batch: 
                    self.status_signal.emit("QUEUE_EXHAUSTED: No more files to process.")
                    break

                prompts = []
                meta = []
                
                # Pre-processing / Windowing
                for fp, path in batch:
                    text = self.decon.extract(path)
                    if not text: continue
                    
                    # 20k character sliding window
                    chunks = [text[i:i+20000] for i in range(0, len(text), 18000)]
                    for idx, c in enumerate(chunks):
                        prompts.append(self._build_p(Path(path).name, c))
                        meta.append((fp, Path(path).name))

                if not prompts: continue
                
                self.status_signal.emit(f"GPU_REASONING: Processing {len(prompts)} segments...")
                outputs = llm.generate(prompts, sampling)
                
                results = []
                for i, out in enumerate(outputs):
                    raw = out.outputs[0].text
                    # Extract objects with regex to ignore chat filler
                    items = re.findall(r'\{[^{}]*\}', raw)
                    for item in items:
                        try:
                            f = json.loads(item.replace('\n',' '))
                            results.append((
                                meta[i][0], meta[i][1], 
                                str(f.get('source','N/A')), 
                                str(f.get('date','Unknown')), 
                                str(f.get('summary','')), 
                                str(f.get('type','General')), 
                                str(f.get('crime','None')), 
                                1 # Default severity for this pass
                            ))
                        except: continue

                if results:
                    self._save(results)
                    fact_count += len(results)
                    self.fact_signal.emit(results)
                
                proc_count += len(batch)
                self.stats_signal.emit(proc_count, fact_count)

            self.status_signal.emit("ENGINE_IDLE: Session Complete.")
            self.finished_signal.emit()
        except Exception as e:
            self.status_signal.emit(f"CRITICAL: {e}")

    def _build_p(self, fn, txt):
        return f"<|im_start|>system\nExtract JSON: source, date, summary, type, crime, severity.<|im_end|>\n<|im_start|>user\nFILE: {fn}\nDATA: {txt}<|im_end|>\n<|im_start|>assistant\n{{\"findings\": ["

    def _get_batch(self):
        try:
            with self.db.get_connection(self.config.registry_db_path) as conn:
                conn.execute(f"ATTACH DATABASE '{self.config.intelligence_db_path}' AS intel")
                return conn.execute(f"""
                    SELECT fingerprint, path FROM registry 
                    WHERE fingerprint NOT IN (SELECT fingerprint FROM intel.intelligence) 
                    LIMIT {self.config.batch_size}
                """).fetchall()
        except: return []

    def _save(self, data):
        try:
            with self.db.get_connection(self.config.intelligence_db_path) as conn:
                conn.executemany("INSERT OR REPLACE INTO intelligence VALUES (?,?,?,?,?,?,?,?)", data)
                conn.commit()
        except: pass