import json
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class ProjectConfig:
    """Handles investigation-specific settings and hardware allocation."""
    project_name: str = "New Investigation"
    
    # Storage Paths
    source_root: str = ""        # Folder containing VOL folders
    registry_db_path: str = ""   # Local SQLite (for performance)
    intelligence_db_path: str = "" # Final Results (Pi or Local)
    
    # Compute Allocation (Optimized for 7800X3D + 3090)
    vram_allocation: float = 0.40
    context_window: int = 32768
    cpu_workers: int = 16
    batch_size: int = 24
    
    # Operational Toggles
    use_gpu_ocr: bool = False
    use_gpu_whisper: bool = False

    def save(self, filepath: str):
        """Persist settings to a JSON project file."""
        with open(filepath, 'w') as f:
            json.dump(asdict(self), f, indent=4)

    @classmethod
    def load(cls, filepath: str):
        """Load settings from a JSON project file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
            return cls(**data)