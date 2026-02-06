import asyncio
import json
import re
import time
import sqlite3
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Slot
from .deconstructor import Deconstructor
from ..utils.db_handler import SteinLineDB

class AnalysisWorker(QThread):
    # Telemetry Signals
    status_signal = Signal(str)
    stats_signal = Signal(int, int) # (Processed, Facts)
    fact_signal = Signal(list)      # Recent fact row for the table
    finished_signal = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_running = True
        self.db_manager = SteinLineDB(config)
        self.deconstructor = Deconstructor(config)
        
        # Internal counters
        self.processed_count = 0
        self.facts_count = 0

    def run(self):
        """Entry point for the thread."""
        try:
            asyncio.run(self.main_loop())
        except Exception as e:
            self.status_signal.emit(f"CRITICAL ENGINE ERROR: {e}")

    async def main_loop(self):
        self.status_signal.emit("Initializing Neural Reasoner (vLLM)...")
        
        # Late import to prevent GUI slowdown
        from vllm import LLM, SamplingParams
        
        try:
            llm = LLM(
                model="Qwen/Qwen2.5-7B-Instruct-AWQ",
                gpu_memory_utilization=self.config.vram_allocation,
                max_model_len=self.config.context_window,
                enforce_eager=True,
                trust_remote_code=True
            )
            sampling = SamplingParams(temperature=0, max_tokens=2000, repetition_penalty=1.1)
        except Exception as e:
            self.status_signal.emit(f"GPU Init Failed: {e}")
            return

        self.status_signal.emit("Engine Active. Starting Extraction...")

        while self.is_running:
            # 1. Fetch batch from Registry
            batch = self._get_work_batch()
            if not batch:
                self.status_signal.emit("No more unprocessed files found.")
                break

            # 2. Deconstruct (CPU)
            segments = []
            metadata = [] # (fp, fn)
            
            for fp, path in batch:
                try:
                    text = self.deconstructor.extract(path)
                    if not text: continue
                    
                    # Recursive Windowing (20k chars)
                    MAX_CHARS = 20000
                    OVERLAP = 2000
                    
                    if len(text) <= MAX_CHARS:
                        segments.append(self._build_prompt(Path(path).name, text))
                        metadata.append((fp, Path(path).name))
                    else:
                        start = 0
                        while start < len(text):
                            chunk = text[start : start + MAX_CHARS]
                            segments.append(self._build_prompt(f"{Path(path).name} (Part {start//MAX_CHARS})", chunk))
                            metadata.append((fp, Path(path).name))
                            start += (MAX_CHARS - OVERLAP)
                except Exception as e:
                    self.status_signal.emit(f"Skip {Path(path).name}: {e}")

            if not segments: continue

            # 3. Reason (GPU)
            self.status_signal.emit(f"Reasoning on {len(segments)} text segments...")
            outputs = llm.generate(segments, sampling)

            # 4. Parse & Persist
            final_facts = []
            for i, out in enumerate(outputs):
                raw_text = out.outputs[0].text
                # Robust Regex Recovery
                potential_items = re.findall(r'\{[^{}]*\}', raw_text)
                for item_str in potential_items:
                    try:
                        f = json.loads(item_str.replace('\n', ' ').strip())
                        fact = (
                            metadata[i][0], # fp
                            metadata[i][1], # fn
                            str(f.get('source', 'N/A')),
                            str(f.get('date', 'Unknown')),
                            str(f.get('summary', 'No summary')),
                            str(f.get('type', 'General')),
                            str(f.get('crime', 'None')),
                            int(re.search(r'\d+', str(f.get('severity', '1'))).group() or 1)
                        )
                        final_facts.append(fact)
                    except: continue

            if final_facts:
                self._save_facts(final_facts)
                self.facts_count += len(final_facts)
                self.fact_signal.emit(final_facts[:5]) # Send a sample for the UI table

            self.processed_count += len(batch)
            self.stats_signal.emit(self.processed_count, self.facts_extracted)

        self.status_signal.emit("Pipeline Shutdown.")
        self.finished_signal.emit()

    def _get_work_batch(self):
        """Fetch files that exist in Registry but not in Intelligence."""
        # Note: To avoid network hangs, we do a simple diffing query
        try:
            with self.db_manager.get_connection(self.config.registry_db_path) as conn:
                # Attach the intelligence DB for the diff check
                conn.execute(f"ATTACH DATABASE '{self.config.intelligence_db_path}' AS intel")
                cursor = conn.execute(f"""
                    SELECT fingerprint, path FROM registry 
                    WHERE fingerprint NOT IN (SELECT fingerprint FROM intel.intelligence)
                    LIMIT {self.config.batch_size}
                """)
                return cursor.fetchall()
        except Exception as e:
            self.status_signal.emit(f"DB Fetch Error: {e}")
            return []

    def _save_facts(self, facts):
        try:
            with self.db_manager.get_connection(self.config.intelligence_db_path) as conn:
                conn.executemany("INSERT OR REPLACE INTO intelligence VALUES (?,?,?,?,?,?,?,?)", facts)
                conn.commit()
        except Exception as e:
            self.status_signal.emit(f"Save Error: {e}")

    def _build_prompt(self, filename, data):
        return (f"<|im_start|>system\nYou are a forensic analyst. Extract facts into JSON objects with keys: "
                f"source, date, summary, type, crime, severity.<|im_end|>\n"
                f"<|im_start|>user\nFILE: {filename}\nDATA: {data}<|im_end|>\n"
                f"<|im_start|>assistant\n{{\"findings\": [")

    def stop(self):
        self.is_running = False