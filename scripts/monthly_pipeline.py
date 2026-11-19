"""Run the monthly data and model pipeline in a reproducible order."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"


def _run(command: list[str], *, env: dict[str, str]) -> None:
    print("[run]", " ".join(command))
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the monthly Optichain ML pipeline.")
    parser.add_argument("--mode", choices=("incremental", "replace"), default="incremental")
    parser.add_argument("--skip-training", action="store_true")
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND) + os.pathsep + env.get("PYTHONPATH", "")
    env["OPTICHAIN_TRAINING_SOURCE"] = "database"

    _run([sys.executable, "-m", "app.db.ingest", "--force", f"--{args.mode}"], env=env)
    if args.skip_training:
        print("[done] Ingest completed; training skipped.")
        return 0

    _run([sys.executable, "scripts/model1_script.py"], env=env)
    _run([sys.executable, "scripts/seed_and_train_influencer_demo.py", "--source", "database"], env=env)
    _run([sys.executable, "scripts/conti_script.py"], env=env)
    _run([sys.executable, "scripts/train_quantile_models.py", "--source", "database"], env=env)
    print("[done] Monthly ingest and training pipeline completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
