import os
import json
from dataclasses import dataclass, asdict
from .hardware_probe import HardwareProbe

@dataclass
class ProjectConfig:
    """Handles investigation-specific settings and hardware allocation."""
    project_name: str = "New Investigation"
    source_root: str = ""
    registry_db_path: str = ""
    intelligence_db_path: str = ""
    
    # Resource Allocation (Tuned by auto_tune)
    vram_allocation: float = 0.40
    context_window: int = 16384
    cpu_workers: int = 4
    batch_size: int = 24
    ram_limit_gb: float = 8.0
    
    use_gpu_ocr: bool = False
    use_gpu_whisper: bool = False

    compute_vendor: str = "cpu"
    compute_profile: str = "cpu"
    detected_gpu_name: str = "CPU Only"
    llm_backend: str = "cpu-fallback"
    ocr_device: str = "cpu"
    whisper_device: str = "cpu"
    
    is_ready: bool = False

    def auto_tune(self):
        """Interrogate hardware and set optimal defaults."""
        # 1. Detect CPU Threads (Optimized for 7800X3D)
        self.cpu_workers = HardwareProbe.get_cpu_threads()
        total_ram = HardwareProbe.get_total_ram_gb()
        self.ram_limit_gb = round(total_ram * 0.75, 1)
        
        # 2. Detect vendor-agnostic compute capabilities
        capabilities = HardwareProbe.get_compute_capabilities()
        self.compute_vendor = capabilities.get("vendor", "cpu")
        self.compute_profile = capabilities.get("profile", "cpu")
        self.detected_gpu_name = capabilities.get("name", "CPU Only")
        self.llm_backend = capabilities.get("llm_backend", "cpu-fallback")
        self.ocr_device = capabilities.get("ocr_device", "cpu")
        self.whisper_device = capabilities.get("whisper_device", "cpu")

        self.use_gpu_ocr = self.ocr_device == "cuda"
        self.use_gpu_whisper = self.whisper_device == "cuda"

        if self.compute_vendor == "nvidia":
            self.vram_allocation = 0.45
            if float(capabilities.get("total_vram_gb", 0.0)) >= 20:
                self.context_window = 32768
        else:
            self.vram_allocation = 0.0
            self.context_window = min(self.context_window, 8192)

    def validate(self) -> bool:
        """Verify that all paths are set and accessible."""
        if not self.source_root: return False
        
        # Clean paths
        self.source_root = self.source_root.strip()
        self.registry_db_path = self.registry_db_path.strip()
        self.intelligence_db_path = self.intelligence_db_path.strip()

        if os.path.exists(self.source_root) and self.registry_db_path and self.intelligence_db_path:
            self.is_ready = True
            return True
        
        self.is_ready = False
        return False

    def save(self, filepath: str):
        """Save config to JSON."""
        with open(filepath, 'w') as f:
            json.dump(asdict(self), f, indent=4)

    @classmethod
    def load(cls, filepath: str):
        """Load config from JSON. Returns a new instance if file fails."""
        if not os.path.exists(filepath):
            return cls()
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                return cls(**data)
        except Exception:
            return cls()