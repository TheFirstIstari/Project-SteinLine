from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, 
                             QSpinBox, QGroupBox, QLabel, QProgressBar)
from PySide6.QtCore import QTimer, Qt
import psutil
import sqlite3
from pathlib import Path

class PerformanceDashboard(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.init_ui()
        
        # Timer for live telemetry updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_telemetry)
        self.timer.start(1000) # Update every 1s

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. LIVE MONITORING
        mon_group = QGroupBox("SYSTEM_TELEMETRY")
        mon_layout = QFormLayout(mon_group)
        
        self.ram_bar = QProgressBar()
        self.ram_bar.setStyleSheet("QProgressBar::chunk { background-color: #388bfd; }")
        mon_layout.addRow("System RAM Usage:", self.ram_bar)
        
        self.vram_label = QLabel("GPU_VRAM: Detecting...")
        mon_layout.addRow("Inference VRAM:", self.vram_label)
        
        layout.addWidget(mon_group)

        # 2. RESOURCE LIMITS (TUNABLES)
        limit_group = QGroupBox("HARDWARE_CAPS")
        form = QFormLayout(limit_group)

        self.ram_spin = QDoubleSpinBox()
        self.ram_spin.setRange(2.0, 512.0)
        self.ram_spin.setValue(self.config.ram_limit_gb)
        self.ram_spin.valueChanged.connect(self._sync_config)
        form.addRow("Max RAM Usage (GB):", self.ram_spin)

        self.vram_spin = QDoubleSpinBox()
        self.vram_spin.setRange(0.1, 0.95)
        self.vram_spin.setValue(self.config.vram_allocation)
        self.vram_spin.valueChanged.connect(self._sync_config)
        form.addRow("vLLM VRAM Limit (%):", self.vram_spin)

        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 64)
        self.thread_spin.setValue(self.config.cpu_workers)
        self.thread_spin.valueChanged.connect(self._sync_config)
        form.addRow("Worker Threads:", self.thread_spin)

        layout.addWidget(limit_group)

        # 3. BENCHMARK SUMMARY
        bench_group = QGroupBox("BENCHMARK_SUMMARY")
        bench_form = QFormLayout(bench_group)

        self.bench_last = QLabel("No benchmark runs yet")
        self.bench_status = QLabel("Status: -")
        self.bench_scenario = QLabel("Scenario: -")
        self.bench_elapsed = QLabel("Latest elapsed: -")
        self.bench_trend = QLabel("Trend (last 5): -")

        bench_form.addRow("Last Run:", self.bench_last)
        bench_form.addRow("Run Status:", self.bench_status)
        bench_form.addRow("Scenario:", self.bench_scenario)
        bench_form.addRow("Elapsed:", self.bench_elapsed)
        bench_form.addRow("Trend:", self.bench_trend)

        layout.addWidget(bench_group)
        layout.addStretch()

    def _update_telemetry(self):
        mem = psutil.virtual_memory()
        self.ram_bar.setValue(int(mem.percent))
        
        # Check if we are over the limit
        current_gb = mem.used / (1024**3)
        if current_gb > self.config.ram_limit_gb:
            self.ram_bar.setStyleSheet("QProgressBar::chunk { background-color: #f85149; }")
        else:
            self.ram_bar.setStyleSheet("QProgressBar::chunk { background-color: #388bfd; }")

        self._update_benchmark_summary()

    def _update_benchmark_summary(self):
        db_path = Path(getattr(self.config, "benchmark_db_path", "benchmarks/steinline_benchmarks.db"))
        if not db_path.exists():
            self.bench_last.setText("No benchmark runs yet")
            self.bench_status.setText("Status: -")
            self.bench_scenario.setText("Scenario: -")
            self.bench_elapsed.setText("Latest elapsed: -")
            self.bench_trend.setText("Trend (last 5): -")
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            latest = cur.execute(
                """
                SELECT run_id, started_at, status, scenario
                FROM benchmark_runs
                ORDER BY id DESC LIMIT 1
                """
            ).fetchone()

            if not latest:
                self.bench_last.setText("No benchmark runs yet")
                return

            run_id, started_at, status, scenario = latest
            elapsed_row = cur.execute(
                """
                SELECT value FROM benchmark_metrics
                WHERE run_id = ? AND stage = 'system' AND metric = 'elapsed_total'
                ORDER BY id DESC LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            elapsed_val = float(elapsed_row[0]) if elapsed_row else 0.0

            recent_rows = cur.execute(
                """
                SELECT m.value
                FROM benchmark_runs r
                JOIN benchmark_metrics m ON m.run_id = r.run_id
                WHERE m.stage = 'system' AND m.metric = 'elapsed_total'
                ORDER BY r.id DESC
                LIMIT 5
                """
            ).fetchall()
            recent_vals = [float(r[0]) for r in recent_rows if r and r[0] is not None]

            self.bench_last.setText(f"{run_id[:8]}… @ {started_at}")
            self.bench_status.setText(f"Status: {status}")
            self.bench_scenario.setText(f"Scenario: {scenario}")
            self.bench_elapsed.setText(f"Latest elapsed: {elapsed_val:.2f}s")

            if len(recent_vals) >= 2:
                latest_v = recent_vals[0]
                prior_avg = sum(recent_vals[1:]) / max(1, len(recent_vals) - 1)
                if prior_avg > 0:
                    delta_pct = ((latest_v - prior_avg) / prior_avg) * 100.0
                    direction = "slower" if delta_pct > 0 else "faster"
                    self.bench_trend.setText(f"Trend (last 5): {abs(delta_pct):.1f}% {direction}")
                else:
                    self.bench_trend.setText("Trend (last 5): insufficient baseline")
            else:
                self.bench_trend.setText("Trend (last 5): collect more runs")
        except Exception:
            self.bench_trend.setText("Trend (last 5): unavailable")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _sync_config(self):
        self.config.ram_limit_gb = self.ram_spin.value()
        self.config.vram_allocation = self.vram_spin.value()
        self.config.cpu_workers = self.thread_spin.value()