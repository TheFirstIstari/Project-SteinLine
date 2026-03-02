from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QProgressBar, QFrame)
from PySide6.QtCore import Signal, Slot, Qt, QTimer # ADDED Slot
from datetime import datetime
import time
from ..core.registry_worker import RegistryWorker
from ..core.analysis_worker import AnalysisWorker

class AnalysisPage(QWidget):
    engine_started_signal = Signal(object)
    worker_state_signal = Signal(str)

    def __init__(self, config, console):
        super().__init__()
        self.config = config
        self.console = console
        self.reg_worker = None
        self.inf_worker = None
        self.reg_elapsed_base = 0.0
        self.inf_elapsed_base = 0.0
        self.reg_started_at = None
        self.inf_started_at = None
        self.init_ui()

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self._tick_elapsed)
        self.elapsed_timer.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 1. Registry Task
        self.reg_box = self._create_task_box(
            "STEP_01: FILE_FINGERPRINTING", 
            self.run_reg, self.pause_reg, self.stop_reg
        )
        self.reg_pbar = QProgressBar()
        self.reg_pbar.setStyleSheet("QProgressBar { height: 10px; }")
        self.reg_box.layout().addWidget(self.reg_pbar)

        self.reg_status = QLabel("STATE: IDLE")
        self.reg_status.setStyleSheet("font-family: monospace; font-size: 10px; color: #9da7b3;")
        self.reg_box.layout().addWidget(self.reg_status)
        
        # ADDED: Explicit stat label for Hashing
        self.reg_stats = QLabel("STAT: IDLE")
        self.reg_stats.setStyleSheet("font-family: monospace; font-size: 10px; color: #768390;")
        self.reg_box.layout().addWidget(self.reg_stats)

        self.reg_elapsed = QLabel("ELAPSED: 00:00:00")
        self.reg_elapsed.setStyleSheet("font-family: monospace; font-size: 10px; color: #768390;")
        self.reg_box.layout().addWidget(self.reg_elapsed)

        self.reg_last = QLabel("LAST: -")
        self.reg_last.setStyleSheet("font-family: monospace; font-size: 10px; color: #9da7b3;")
        self.reg_box.layout().addWidget(self.reg_last)
        
        layout.addWidget(self.reg_box)

        # 2. Inference Task
        self.inf_box = self._create_task_box(
            "STEP_02: NEURAL_REASONING", 
            self.run_inf, self.pause_inf, self.stop_inf
        )
        self.inf_status = QLabel("STATE: IDLE")
        self.inf_status.setStyleSheet("font-family: monospace; font-size: 10px; color: #9da7b3;")
        self.inf_box.layout().addWidget(self.inf_status)
        self.inf_stats = QLabel("STAT: IDLE")
        self.inf_stats.setStyleSheet("font-family: monospace; font-size: 10px; color: #768390;")
        self.inf_box.layout().addWidget(self.inf_stats)

        self.inf_elapsed = QLabel("ELAPSED: 00:00:00")
        self.inf_elapsed.setStyleSheet("font-family: monospace; font-size: 10px; color: #768390;")
        self.inf_box.layout().addWidget(self.inf_elapsed)

        self.inf_last = QLabel("LAST: -")
        self.inf_last.setStyleSheet("font-family: monospace; font-size: 10px; color: #9da7b3;")
        self.inf_box.layout().addWidget(self.inf_last)
        layout.addWidget(self.inf_box)

        self.set_session_ready(self.config.is_ready)
        
        layout.addStretch()

    def set_session_ready(self, ready: bool):
        self.reg_box.start_btn.setEnabled(ready)
        self.inf_box.start_btn.setEnabled(ready)
        self.reg_box.pause_btn.setEnabled(False)
        self.reg_box.stop_btn.setEnabled(False)
        self.inf_box.pause_btn.setEnabled(False)
        self.inf_box.stop_btn.setEnabled(False)
        self.reg_box.pause_btn.setText("Pause")
        self.inf_box.pause_btn.setText("Pause")
        self._set_reg_state("READY" if ready else "WAITING_FOR_INIT")
        self._set_inf_state("READY" if ready else "WAITING_FOR_INIT")

    def _format_elapsed(self, seconds: float) -> str:
        total = max(0, int(seconds))
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _set_reg_last(self, result: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.reg_last.setText(f"LAST: {result} @ {ts}")

    def _set_inf_last(self, result: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.inf_last.setText(f"LAST: {result} @ {ts}")

    def _tick_elapsed(self):
        reg_total = self.reg_elapsed_base
        if self.reg_started_at is not None:
            reg_total += time.monotonic() - self.reg_started_at
        self.reg_elapsed.setText(f"ELAPSED: {self._format_elapsed(reg_total)}")

        inf_total = self.inf_elapsed_base
        if self.inf_started_at is not None:
            inf_total += time.monotonic() - self.inf_started_at
        self.inf_elapsed.setText(f"ELAPSED: {self._format_elapsed(inf_total)}")

    def _set_reg_state(self, state: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.reg_status.setText(f"STATE: {state} @ {ts}")
        self.worker_state_signal.emit(f"FINGERPRINTING {state}")

    def _set_inf_state(self, state: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.inf_status.setText(f"STATE: {state} @ {ts}")
        self.worker_state_signal.emit(f"REASONING {state}")

    def _create_task_box(self, title, start_f, pause_f, stop_f):
        frame = QFrame()
        frame.setStyleSheet("background-color: #1c2128; border-radius: 6px; padding: 15px;")
        l = QVBoxLayout(frame)
        l.addWidget(QLabel(title))
        btns = QHBoxLayout()
        start = QPushButton("Start"); pause = QPushButton("Pause"); stop = QPushButton("Cancel")
        start.clicked.connect(start_f); pause.clicked.connect(pause_f); stop.clicked.connect(stop_f)
        for b in [start, pause, stop]: btns.addWidget(b)
        l.addLayout(btns)
        
        # Internal reference to buttons for state management
        frame.start_btn = start
        frame.pause_btn = pause
        frame.stop_btn = stop
        return frame

    # --- ADDED: EXPLICIT SLOTS TO PREVENT C++ CRASHES ---
    
    @Slot(int, int)
    def _update_reg_progress(self, current, total):
        self.reg_stats.setText(f"HASHING: {current:,} / {total:,} files")

    @Slot(int, int)
    def _update_inf_progress(self, processed, facts):
        self.inf_stats.setText(f"PROCESSED: {processed:,} | FACTS_FOUND: {facts:,}")

    @Slot(int)
    def _reg_finished(self, count):
        self.console.append_log(f"TASK_COMPLETE: Fingerprinting finished. {count:,} items synced.")
        if self.reg_started_at is not None:
            self.reg_elapsed_base += time.monotonic() - self.reg_started_at
            self.reg_started_at = None
        self.reg_box.start_btn.setEnabled(self.config.is_ready)
        self.reg_box.pause_btn.setEnabled(False)
        self.reg_box.stop_btn.setEnabled(False)
        self.reg_box.pause_btn.setText("Pause")
        self._set_reg_state("IDLE")
        self._set_reg_last("SUCCESS")

    @Slot()
    def _inf_finished(self):
        self.console.append_log("TASK_COMPLETE: Neural Reasoning Engine cycle complete.")
        if self.inf_started_at is not None:
            self.inf_elapsed_base += time.monotonic() - self.inf_started_at
            self.inf_started_at = None
        self.inf_box.start_btn.setEnabled(self.config.is_ready)
        self.inf_box.pause_btn.setEnabled(False)
        self.inf_box.stop_btn.setEnabled(False)
        self.inf_box.pause_btn.setText("Pause")
        self._set_inf_state("IDLE")
        self._set_inf_last("SUCCESS")

    # --- UPDATED REGISTRY LOGIC ---
    def run_reg(self):
        if not self.config.is_ready:
            self.console.append_log("COMMAND_REJECTED: Initialize project paths first.")
            self._set_reg_state("REJECTED_NOT_READY")
            self._set_reg_last("REJECTED")
            return
        
        self.console.append_log("TASK_START: File Fingerprinting Scan initiated.")
        self.reg_elapsed_base = 0.0
        self.reg_started_at = time.monotonic()
        self.reg_box.start_btn.setEnabled(False)
        self.reg_box.pause_btn.setEnabled(True)
        self.reg_box.stop_btn.setEnabled(True)
        self._set_reg_state("RUNNING")
        
        self.reg_worker = RegistryWorker(self.config)
        self.reg_worker.status_signal.connect(self.console.append_log)
        self.reg_worker.progress_signal.connect(self.reg_pbar.setValue)
        
        # CONNECTING TO EXPLICIT SLOTS INSTEAD OF LAMBDAS
        self.reg_worker.stats_signal.connect(self._update_reg_progress)
        self.reg_worker.finished_signal.connect(self._reg_finished)
        
        self.reg_worker.start()

    def pause_reg(self):
        if self.reg_worker:
            self.reg_worker.toggle_pause()
            status = "RESUMED" if not self.reg_worker.is_paused else "PAUSED"
            self.console.append_log(f"COMMAND_SENT: Fingerprinting process {status}.")
            self.reg_box.pause_btn.setText("Resume" if self.reg_worker.is_paused else "Pause")
            self._set_reg_state("PAUSED" if self.reg_worker.is_paused else "RUNNING")
            if self.reg_worker.is_paused:
                if self.reg_started_at is not None:
                    self.reg_elapsed_base += time.monotonic() - self.reg_started_at
                    self.reg_started_at = None
            else:
                if self.reg_started_at is None:
                    self.reg_started_at = time.monotonic()

    def stop_reg(self):
        if self.reg_worker:
            self.console.append_log("COMMAND_SENT: Cancel request for Fingerprinting.")
            self.reg_worker.stop()
            if self.reg_started_at is not None:
                self.reg_elapsed_base += time.monotonic() - self.reg_started_at
                self.reg_started_at = None
            self.reg_box.start_btn.setEnabled(self.config.is_ready)
            self.reg_box.pause_btn.setEnabled(False)
            self.reg_box.stop_btn.setEnabled(False)
            self.reg_box.pause_btn.setText("Pause")
            self._set_reg_state("CANCELLING")
            self._set_reg_last("CANCELLED")

    # --- UPDATED REASONER LOGIC ---
    def run_inf(self):
        if not self.config.is_ready:
            self.console.append_log("COMMAND_REJECTED: Initialize project paths first.")
            self._set_inf_state("REJECTED_NOT_READY")
            self._set_inf_last("REJECTED")
            return
            
        self.console.append_log("TASK_START: Neural Reasoning Engine requested.")
        self.inf_elapsed_base = 0.0
        self.inf_started_at = time.monotonic()
        self.inf_box.start_btn.setEnabled(False)
        self.inf_box.pause_btn.setEnabled(True)
        self.inf_box.stop_btn.setEnabled(True)
        self._set_inf_state("RUNNING")
        
        self.inf_worker = AnalysisWorker(self.config)
        self.inf_worker.status_signal.connect(self.console.append_log)
        
        # CONNECTING TO EXPLICIT SLOTS
        self.inf_worker.stats_signal.connect(self._update_inf_progress)
        self.inf_worker.finished_signal.connect(self._inf_finished)
        
        try:
            from ..utils.signals import safe_emit
            safe_emit(self.engine_started_signal, self.inf_worker)
        except Exception:
            try:
                import sys
                sys.stderr.write(f"ENGINE_STARTED: {self.inf_worker}\n")
            except Exception:
                pass
        self.inf_worker.start()

    def pause_inf(self):
        if self.inf_worker:
            self.inf_worker.toggle_pause()
            status = "RESUMED" if not self.inf_worker.is_paused else "PAUSED"
            self.console.append_log(f"COMMAND_SENT: Reasoning engine {status}.")
            self.inf_box.pause_btn.setText("Resume" if self.inf_worker.is_paused else "Pause")
            self._set_inf_state("PAUSED" if self.inf_worker.is_paused else "RUNNING")
            if self.inf_worker.is_paused:
                if self.inf_started_at is not None:
                    self.inf_elapsed_base += time.monotonic() - self.inf_started_at
                    self.inf_started_at = None
            else:
                if self.inf_started_at is None:
                    self.inf_started_at = time.monotonic()

    def stop_inf(self):
        if self.inf_worker:
            self.console.append_log("COMMAND_SENT: Cancel request for Reasoning Engine.")
            self.inf_worker.stop()
            if self.inf_started_at is not None:
                self.inf_elapsed_base += time.monotonic() - self.inf_started_at
                self.inf_started_at = None
            self.inf_box.start_btn.setEnabled(self.config.is_ready)
            self.inf_box.pause_btn.setEnabled(False)
            self.inf_box.stop_btn.setEnabled(False)
            self.inf_box.pause_btn.setText("Pause")
            self._set_inf_state("CANCELLING")
            self._set_inf_last("CANCELLED")