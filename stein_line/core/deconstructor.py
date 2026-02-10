import os
from pathlib import Path
import fitz  # PyMuPDF
from faster_whisper import WhisperModel
import easyocr
import logging

# Suppress verbose logging from sub-libraries
logging.getLogger("ppocr").setLevel(logging.ERROR)

class Deconstructor:
    """CPU-bound worker responsible for transforming media into text."""

    def __init__(self, config):
        self.config = config
        
        # Initialize OCR (Forced to CPU to save VRAM for the Reasoner)
        self.ocr = easyocr.Reader(['en'], gpu=self.config.use_gpu_ocr)
        
        # Initialize Whisper (Optimized for CPU with int8)
        device = "cuda" if self.config.use_gpu_whisper else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        self.whisper = WhisperModel("base", device=device, compute_type=compute_type)

    def extract(self, file_path: str) -> str:
        """Routes the file to the appropriate extraction engine."""
        # Validate input early
        if not file_path or not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Skip extremely large files to avoid OOM (safeguard)
        try:
            size = Path(file_path).stat().st_size
            if size > 2 * 1024 * 1024 * 1024:  # 2GB
                raise ValueError(f"File too large: {file_path}")
        except Exception:
            # If stat fails, continue but guard against reading
            pass

        ext = Path(file_path).suffix.lower()

        try:
            if ext == ".pdf":
                return self._process_pdf(file_path)
            elif ext in [".mp4", ".mov", ".m4v", ".mp3", ".wav"]:
                return self._process_audio(file_path)
            elif ext in [".jpg", ".jpeg", ".png", ".bmp"]:
                return self._process_image(file_path)
            else:
                # Unknown types are ignored
                return ""
        except Exception as e:
            # Re-raise with context to be handled by caller
            raise RuntimeError(f"Extraction failed for {file_path}: {str(e)}")

    def _process_pdf(self, path: str) -> str:
        """Extracts digital text; falls back to OCR for scanned pages."""
        text_content = []
        with fitz.open(path) as doc:
            for page in doc:
                page_text = page.get_text().strip()
                if len(page_text) < 100:
                    # Likely a scanned image - rasterize and OCR
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    ocr_results = self.ocr.readtext(img_bytes, detail=0)
                    page_text = " ".join(ocr_results)
                text_content.append(page_text)
        return "\n".join(text_content)

    def _process_audio(self, path: str) -> str:
        """Transcribes audio/video tracks into text stream."""
        segments, _ = self.whisper.transcribe(path, beam_size=5)
        return " ".join([segment.text for segment in segments])

    def _process_image(self, path: str) -> str:
        """Performs computer vision OCR on standalone image files."""
        results = self.ocr.readtext(path, detail=0)
        return " ".join(results)