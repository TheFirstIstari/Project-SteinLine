import json
import time
from pathlib import Path

class CheckpointManager:
    def __init__(self, config):
        self.config = config
        # store checkpoint next to the intelligence DB
        try:
            self.checkpoint_path = Path(self.config.intelligence_db_path).with_suffix('.checkpoint.json')
        except Exception:
            self.checkpoint_path = Path('steinline.checkpoint.json')

    def save_state(self, processed_count: int, last_fingerprint: str = "", total_facts: int = 0):
        state = {
            'processed': int(processed_count),
            'last_fp': str(last_fingerprint),
            'total_facts': int(total_facts),
            'timestamp': time.time()
        }
        try:
            with open(self.checkpoint_path, 'w') as f:
                json.dump(state, f)
        except Exception:
            pass

    def load_state(self):
        if not self.checkpoint_path.exists():
            return None
        try:
            with open(self.checkpoint_path, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def clear(self):
        try:
            if self.checkpoint_path.exists():
                self.checkpoint_path.unlink()
        except Exception:
            pass
