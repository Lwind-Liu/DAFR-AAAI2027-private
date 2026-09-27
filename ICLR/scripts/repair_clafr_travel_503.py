from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(r"C:\Users\f1567\Desktop\AAAI")
AUTODOJO_ROOT = ROOT / "external" / "official_baselines" / "AutoDojo"
RESULT_ROOT = ROOT / "ICLR" / "results" / "agentdojo_v122_claudehaiku45_anthropic_v1"
MODEL = "claude-haiku-4-5-20251001"


def main() -> int:
    if not os.environ.get("OPENAI_COMPATIBLE_API_KEY"):
        raise RuntimeError("OPENAI_COMPATIBLE_API_KEY is required")

    base = [
        sys.executable,
        "-m",
        "agentdojo.scripts.benchmark",
        "--model",
        MODEL,
        "--model-id",
        MODEL,
        "--benchmark-version",
        "v1.2.2",
        "--suite",
        "travel",
        "--logdir",
        str(RESULT_ROOT),
        "--defense",
        "clafr",
        "--attack",
        "important_instructions",
    ]
    commands = (
        base
        + [
            "--user-task",
            "user_task_10",
            "--injection-task",
            "injection_task_4",
            "--injection-task",
            "injection_task_5",
            "--injection-task",
            "injection_task_6",
        ],
        base
        + [
            "--user-task",
            "user_task_11",
            "--injection-task",
            "injection_task_0",
            "--injection-task",
            "injection_task_1",
            "--injection-task",
            "injection_task_2",
            "--injection-task",
            "injection_task_3",
            "--injection-task",
            "injection_task_4",
        ],
    )
    log_path = RESULT_ROOT / "logs" / "repair-clafr-travel-503-v2.log"
    with log_path.open("a", encoding="utf-8") as log:
        for command in commands:
            result = subprocess.run(
                command,
                cwd=AUTODOJO_ROOT,
                env=os.environ,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            log.write(f"===== END exit={result.returncode} =====\n")
            log.flush()
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
