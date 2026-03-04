import argparse
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

import psutil

from stein_line.utils.db_handler import SteinLineDB
from stein_line.utils.project_config import ProjectConfig


def iter_files(root: str, max_files: int):
    allowed = {
        ".pdf", ".txt", ".md", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".bmp",
        ".tif", ".tiff", ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".m4v"
    }
    collected = []
    for base, _, files in os.walk(root):
        for name in files:
            p = Path(base) / name
            if p.suffix.lower() in allowed:
                collected.append(p)
                if len(collected) >= max_files:
                    return collected
    return collected


def hash_file(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def metric(db_path: str, run_id: str, stage: str, name: str, value: float, unit: str):
    SteinLineDB.benchmark_metric(db_path, run_id, stage, name, value, unit)


def run_registry_bench(files, db_path, run_id):
    t0 = time.perf_counter()
    hashed = 0
    for p in files:
        try:
            hash_file(p)
            hashed += 1
        except Exception:
            continue
    elapsed = max(0.0001, time.perf_counter() - t0)
    metric(db_path, run_id, "registry", "files_hashed", hashed, "count")
    metric(db_path, run_id, "registry", "elapsed", elapsed, "sec")
    metric(db_path, run_id, "registry", "throughput", hashed / elapsed, "files_per_sec")


def run_extract_bench(config: ProjectConfig, files, db_path, run_id):
    try:
        from stein_line.core.deconstructor import Deconstructor
    except ModuleNotFoundError as e:
        metric(db_path, run_id, "extract", "skipped", 1, "flag")
        metric(db_path, run_id, "extract", "files_extracted", 0, "count")
        metric(db_path, run_id, "extract", "elapsed", 0.0, "sec")
        metric(db_path, run_id, "extract", "throughput", 0.0, "files_per_sec")
        return f"extract stage skipped: missing dependency ({e.name})"

    extractor = Deconstructor(config)
    t0 = time.perf_counter()
    extracted = 0
    total_chars = 0
    for p in files:
        try:
            text = extractor.extract(str(p))
            if text:
                extracted += 1
                total_chars += len(text)
        except Exception:
            continue

    elapsed = max(0.0001, time.perf_counter() - t0)
    metric(db_path, run_id, "extract", "files_extracted", extracted, "count")
    metric(db_path, run_id, "extract", "chars_out", total_chars, "chars")
    metric(db_path, run_id, "extract", "elapsed", elapsed, "sec")
    metric(db_path, run_id, "extract", "throughput", extracted / elapsed, "files_per_sec")
    return "extract stage completed"


def run_reasoning_bench(config: ProjectConfig, db_path, run_id):
    sample = "Incident summary: multiple entities observed near site on 2025-10-12."
    t0 = time.perf_counter()

    backend = getattr(config, "llm_backend", "cpu-fallback")
    status = "cpu_fallback"
    out_len = 0

    if backend == "vllm":
        try:
            from vllm import LLM, SamplingParams

            llm = LLM(
                model="Qwen/Qwen2.5-7B-Instruct-AWQ",
                gpu_memory_utilization=max(0.2, float(getattr(config, "vram_allocation", 0.45))),
                max_model_len=min(int(getattr(config, "context_window", 8192)), 8192),
                enforce_eager=True,
                trust_remote_code=True,
            )
            sampling = SamplingParams(temperature=0, max_tokens=128)
            outputs = llm.generate([sample], sampling)
            out_len = len(outputs[0].outputs[0].text) if outputs and outputs[0].outputs else 0
            status = "vllm"
        except Exception:
            status = "vllm_failed_fallback"
            out_len = len(sample[:200])
    else:
        out_len = len(sample[:200])

    elapsed = max(0.0001, time.perf_counter() - t0)
    metric(db_path, run_id, "reasoning", "elapsed", elapsed, "sec")
    metric(db_path, run_id, "reasoning", "output_len", out_len, "chars")
    metric(db_path, run_id, "reasoning", "mode", 1 if "vllm" in status else 0, "vllm_flag")


def run_full(args):
    config = ProjectConfig.load(args.config)
    config.auto_tune()

    if args.source_root:
        config.source_root = args.source_root

    source_root = config.source_root or str(Path.cwd())
    if not Path(source_root).exists():
        raise RuntimeError("Source root missing. Set --source-root or initialize project config first.")

    files = iter_files(source_root, args.max_files)
    if not files:
        raise RuntimeError("No benchmarkable files found in source root.")

    db_path = args.db_path
    run_id = str(uuid.uuid4())

    SteinLineDB.init_benchmark_schema(db_path)
    SteinLineDB.benchmark_start(
        db_path,
        run_id,
        args.scenario,
        getattr(config, "compute_profile", "cpu"),
        getattr(config, "detected_gpu_name", "CPU Only"),
    )

    proc = psutil.Process()
    rss_start = proc.memory_info().rss / (1024 * 1024)
    metric(db_path, run_id, "system", "rss_start", rss_start, "mb")

    t_all = time.perf_counter()
    notes = []
    try:
        if args.scenario in ("registry", "full"):
            run_registry_bench(files, db_path, run_id)

        if args.scenario in ("extract", "full"):
            notes.append(run_extract_bench(config, files, db_path, run_id))

        if args.scenario in ("reasoning", "full"):
            run_reasoning_bench(config, db_path, run_id)

        total_elapsed = max(0.0001, time.perf_counter() - t_all)
        rss_end = proc.memory_info().rss / (1024 * 1024)
        metric(db_path, run_id, "system", "rss_end", rss_end, "mb")
        metric(db_path, run_id, "system", "elapsed_total", total_elapsed, "sec")

        summary_note = "; ".join([f"files={len(files)}"] + notes)
        SteinLineDB.benchmark_finish(db_path, run_id, "success", notes=summary_note)

        print(json.dumps({
            "run_id": run_id,
            "status": "success",
            "scenario": args.scenario,
            "files_considered": len(files),
            "compute_profile": getattr(config, "compute_profile", "cpu"),
            "device": getattr(config, "detected_gpu_name", "CPU Only"),
            "db_path": db_path,
            "notes": notes,
        }, indent=2))
    except Exception as e:
        SteinLineDB.benchmark_finish(db_path, run_id, "failed", notes=str(e))
        raise


def main():
    parser = argparse.ArgumentParser(description="SteinLine benchmark runner")
    parser.add_argument("--scenario", choices=["registry", "extract", "reasoning", "full"], default="full")
    parser.add_argument("--config", default="last_project.json")
    parser.add_argument("--source-root", default="")
    parser.add_argument("--max-files", type=int, default=50)
    parser.add_argument("--db-path", default="benchmarks/steinline_benchmarks.db")
    args = parser.parse_args()

    run_full(args)


if __name__ == "__main__":
    main()
