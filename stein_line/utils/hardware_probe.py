import psutil
import logging
import subprocess
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
    def _detect_lspci_gpus() -> dict:
        info = {
            "amd_found": False,
            "intel_igpu_found": False,
            "amd_name": "",
            "intel_igpu_name": "",
        }

        try:
            output = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL)
            for line in output.splitlines():
                lowered = line.lower()
                if "vga" not in lowered and "3d controller" not in lowered and "display controller" not in lowered:
                    continue

                if "amd" in lowered or "ati" in lowered:
                    info["amd_found"] = True
                    if not info["amd_name"]:
                        info["amd_name"] = line.strip()

                if "intel" in lowered:
                    info["intel_igpu_found"] = True
                    if not info["intel_igpu_name"]:
                        info["intel_igpu_name"] = line.strip()
        except Exception:
            pass

        return info

    @staticmethod
    def get_compute_capabilities() -> dict:
        """Returns normalized compute capabilities for backend selection."""
        nvidia = HardwareProbe.get_gpu_info()
        pci = HardwareProbe._detect_lspci_gpus()

        capabilities = {
            "gpu_found": False,
            "vendor": "cpu",
            "name": "CPU Only",
            "total_vram_gb": 0.0,
            "nvidia_available": nvidia.get("gpu_found", False),
            "amd_available": pci.get("amd_found", False),
            "integrated_gpu_available": pci.get("intel_igpu_found", False),
            "llm_backend": "cpu-fallback",
            "ocr_device": "cpu",
            "whisper_device": "cpu",
            "profile": "cpu",
        }

        if nvidia.get("gpu_found", False):
            capabilities["gpu_found"] = True
            capabilities["vendor"] = "nvidia"
            capabilities["name"] = nvidia.get("name", "NVIDIA GPU")
            capabilities["total_vram_gb"] = float(nvidia.get("total_vram_gb", 0.0))
            capabilities["llm_backend"] = "vllm"
            capabilities["ocr_device"] = "cuda"
            capabilities["whisper_device"] = "cuda"
            capabilities["profile"] = "nvidia"
            return capabilities

        if pci.get("amd_found", False):
            capabilities["gpu_found"] = True
            capabilities["vendor"] = "amd"
            capabilities["name"] = pci.get("amd_name") or "AMD GPU"
            capabilities["llm_backend"] = "cpu-fallback"
            capabilities["ocr_device"] = "cpu"
            capabilities["whisper_device"] = "cpu"
            capabilities["profile"] = "amd-fallback"
            return capabilities

        if pci.get("intel_igpu_found", False):
            capabilities["gpu_found"] = True
            capabilities["vendor"] = "intel_igpu"
            capabilities["name"] = pci.get("intel_igpu_name") or "Intel Integrated Graphics"
            capabilities["llm_backend"] = "cpu-fallback"
            capabilities["ocr_device"] = "cpu"
            capabilities["whisper_device"] = "cpu"
            capabilities["profile"] = "igpu-fallback"
            return capabilities

        return capabilities
    
    @staticmethod
    def get_total_ram_gb() -> float:
        """Returns total physical memory in GB."""
        return psutil.virtual_memory().total / (1024**3)