# Project SteinLine

Project SteinLine is an asymmetrical distributed forensic platform designed to process large volumes of documents, images, and video evidence using multimodal AI.

## Core Architecture
- Storage & Registry: Optimized for Raspberry Pi 5 (SSD) or Local Storage.
- Compute & Inference: High-density execution on RTX 3090/4090 using vLLM kernels.
- Visualization: Interactive 2D infinite canvas built with Qt (PySide6).

## Features
- Recursive Windowing: Processing of extremely long documents without information loss.
- Multimodal Pipeline: Integrated PDF deconstruction, OCR, and Audio Transcription.
- Non-Destructive: Source evidence remains read-only at all times.

## Prerequisites
- Linux (Ubuntu 22.04+ recommended) ((other platforms are in the works))
- NVIDIA GPU with 24GB VRAM (for reasonable model performance)
- Python 3.11+