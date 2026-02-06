import json
import os
from dataclasses import dataclass, asdict
from .hardware_probe import HardwareProbe

@dataclass
class ProjectConfig:
    project_name: str = "New Investigation"
    source_root: str = ""
    registry_db_path: str = ""
    intelligence_db_path: str = ""

    
    # Auto-tuned fields
    vram_allocation: float = 0.0
    context_window: int = 16384
    cpu_workers: int = 4
    batch_size: int = 24
    
    use_gpu_ocr: bool = False
    use_gpu_whisper: bool = False

    is_ready: bool = False

    def validate(self) -> bool:
        """Verify that all paths are set and accessible."""
        # Clean paths (remove trailing spaces if any)
        self.source_root = self.source_root.strip()
        self.registry_db_path = self.registry_db_path.strip()
        self.intelligence_db_path = self.intelligence_db_path.strip()

        if self.source_root and os.path.exists(self.source_root) and self.registry_db_path and self.intelligence_db_path:
            self.is_ready = True  # CRITICAL: This unlocks the Analysis Engine buttons
            return True
            
        self.is_ready = False
        return False

    def auto_tune(self):
        """Automatically set optimal defaults based on host hardware."""
        cpu_threads = HardwareProbe.get_cpu_threads()
        gpu = HardwareProbe.get_gpu_info()

        # Set CPU workers to 100% of threads for the 7800X3D
        self.cpu_workers = cpu_threads
        
        if gpu["gpu_found"]:
            # If a high-end GPU is found, default to 45% utilization
            # This leaves room for the OS and display
            self.vram_allocation = 0.45
            self.use_gpu_ocr = True
            self.use_gpu_whisper = True
            # Adjust context window based on VRAM (24GB+ cards get more)
            if gpu["total_vram_gb"] >= 20:
                self.context_window = 32768
        else:
            self.vram_allocation = 0.0
            self.use_gpu_ocr = False
            self.use_gpu_whisper = False

    def save(self, filepath: str):
        with open(filepath, 'w') as f:
            json.dump(asdict(self), f, indent=4)

    @classmethod
    def load(cls, filepath: str):
        with open(filepath, 'r') as f:
            data = json.load(f)
            return cls(**data)