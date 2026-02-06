import psutil
import logging
try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False

class HardwareProbe:
    """Probes the host system to determine optimal processing limits."""

    @staticmethod
    def get_cpu_threads() -> int:
        """Returns the number of logical CPU cores."""
        return psutil.cpu_count(logical=True) or 4

    @staticmethod
    def get_gpu_info() -> dict:
        """Detects NVIDIA GPU presence and total VRAM in GB."""
        info = {"gpu_found": False, "total_vram_gb": 0.0, "name": "CPU Only"}
        
        if not NVML_AVAILABLE:
            return info

        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                info["gpu_found"] = True
                info["total_vram_gb"] = mem_info.total / (1024**3)
                info["name"] = pynvml.nvmlDeviceGetName(handle)
            pynvml.nvmlShutdown()
        except Exception as e:
            logging.warning(f"NVML Probing failed: {e}")
        
        return info
    
    @staticmethod
    def get_total_ram_gb() -> float:
        """Returns total physical memory in GB."""
        return psutil.virtual_memory().total / (1024**3)