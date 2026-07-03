"""End-to-end ingestion orchestrator.

Runs the full TDR ingestion pipeline in order, one phase at a time:

    phase1_extract   → extract raw text (+ OCR fallback) from PDFs in data/raw
    phase0_classifier→ keep only genuine TDR documents (keyword + LLM filter)
    phase2_clean     → normalise whitespace / cleanup
    phase3_chunk     → split cleaned docs into overlapping chunks
    phase4_embed     → embed chunks and index them into Qdrant

Each phase is an independent script that reads/writes JSON files under
backend/data/ and runs its logic at import time. Rather than refactor them,
this orchestrator executes each as a subprocess and stops at the first
failure, so a broken phase doesn't silently corrupt the ones after it.

Usage:
    python -m backend.scripts.run_ingestion

Prerequisites:
    - PDFs placed in backend/data/raw/
    - Qdrant running (docker compose up -d qdrant) for the final embed phase
    - Ollama running (for the phase0 LLM classifier)
"""

import subprocess
import sys
import time

# Fix Unicode output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# Phases run in this exact order. Each entry is (label, module path).
# phase4_embed performs both embedding AND indexing into Qdrant, so there is
# no separate index step here.
PHASES = [
    ("Phase 1 · Extract text (+OCR)", "backend.ingestion.phase1_extract"),
    ("Phase 0 · Classify TDRs", "backend.ingestion.phase0_classifier"),
    ("Phase 2 · Clean text", "backend.ingestion.phase2_clean"),
    ("Phase 3 · Chunk", "backend.ingestion.phase3_chunk"),
    ("Phase 4 · Embed + index", "backend.ingestion.phase4_embed"),
]


def run_phase(label: str, module: str) -> bool:
    """Run one phase as `python -m <module>`. Returns True on success."""
    print("\n" + "=" * 70)
    print(f"▶️  {label}   ({module})")
    print("=" * 70)

    start = time.time()
    # Inherit stdout/stderr so each phase's own progress output streams live.
    result = subprocess.run([sys.executable, "-m", module])
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"\n❌ {label} FAILED (exit code {result.returncode}) after {elapsed:.1f}s")
        return False

    print(f"\n✅ {label} done in {elapsed:.1f}s")
    return True


def main() -> int:
    print("=" * 70)
    print("🚀 TDR INGESTION PIPELINE")
    print("=" * 70)
    print("Running phases: extract → classify → clean → chunk → embed/index")

    overall_start = time.time()

    for label, module in PHASES:
        if not run_phase(label, module):
            print("\n" + "=" * 70)
            print("🛑 Ingestion aborted — a phase failed. Fix the error above and re-run.")
            print("=" * 70)
            return 1

    total = time.time() - overall_start
    print("\n" + "=" * 70)
    print(f"🎉 INGESTION COMPLETE — all {len(PHASES)} phases succeeded in {total:.1f}s")
    print("   Your documents are now embedded and indexed in Qdrant.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
