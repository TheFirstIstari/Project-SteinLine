from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QProgressBar, QFrame)
from PySide6.QtCore import Signal, Slot, Qt # ADDED Slot
from ..core.registry_worker import RegistryWorker
from ..core.analysis_worker import AnalysisWorker

class AnalysisPage(QWidget):
    engine_started_signal = Signal(object)

    def __init__(self, config, console):
        super().__init__()
        self.config = config
        self.console = console
        self.reg_worker = None
        self.inf_worker = None
        self.init_ui()

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
        
        # ADDED: Explicit stat label for Hashing
        self.reg_stats = QLabel("STAT: IDLE")
        self.reg_stats.setStyleSheet("font-family: monospace; font-size: 10px; color: #768390;")
        self.reg_box.layout().addWidget(self.reg_stats)
        
        layout.addWidget(self.reg_box)

        # 2. Inference Task
        self.inf_box = self._create_task_box(
            "STEP_02: NEURAL_REASONING", 
            self.run_inf, self.pause_inf, self.stop_inf
        )
        self.inf_stats = QLabel("STAT: IDLE")
        self.inf_stats.setStyleSheet("font-family: monospace; font-size: 10px; color: #768390;")
        self.inf_box.layout().addWidget(self.inf_stats)
        layout.addWidget(self.inf_box)
        
        layout.addStretch()

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
        self.reg_box.start_btn.setEnabled(True)

    @Slot()
    def _inf_finished(self):
        self.console.append_log("TASK_COMPLETE: Neural Reasoning Engine cycle complete.")
        self.inf_box.start_btn.setEnabled(True)

    # --- UPDATED REGISTRY LOGIC ---
    def run_reg(self):
        if not self.config.is_ready:
            self.console.append_log("COMMAND_REJECTED: Initialize project paths first.")
            return
        
        self.console.append_log("TASK_START: File Fingerprinting Scan initiated.")
        self.reg_box.start_btn.setEnabled(False)
        
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

    def stop_reg(self):
        if self.reg_worker:
            self.console.append_log("COMMAND_SENT: Cancel request for Fingerprinting.")
            self.reg_worker.stop()
            self.reg_box.start_btn.setEnabled(True)

    # --- UPDATED REASONER LOGIC ---
    def run_inf(self):
        if not self.config.is_ready:
            self.console.append_log("COMMAND_REJECTED: Initialize project paths first.")
            return
            
        self.console.append_log("TASK_START: Neural Reasoning Engine requested.")
        self.inf_box.start_btn.setEnabled(False)
        
        self.inf_worker = AnalysisWorker(self.config)
        self.inf_worker.status_signal.connect(self.console.append_log)
        
        # CONNECTING TO EXPLICIT SLOTS
        self.inf_worker.stats_signal.connect(self._update_inf_progress)
        self.inf_worker.finished_signal.connect(self._inf_finished)
        
        self.engine_started_signal.emit(self.inf_worker)
        self.inf_worker.start()

    def pause_inf(self):
        if self.inf_worker:
            self.inf_worker.toggle_pause()
            status = "RESUMED" if not self.inf_worker.is_paused else "PAUSED"
            self.console.append_log(f"COMMAND_SENT: Reasoning engine {status}.")
            self.inf_box.pause_btn.setText("Resume" if self.inf_worker.is_paused else "Pause")

    def stop_inf(self):
        if self.inf_worker:
            self.console.append_log("COMMAND_SENT: Cancel request for Reasoning Engine.")
            self.inf_worker.stop()
            self.inf_box.start_btn.setEnabled(True)