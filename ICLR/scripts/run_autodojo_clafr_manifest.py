from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_autodojo_table_clafr import configure_env, run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run suite-specific CLAFR ablations from a frozen manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--defenses", nargs="+", default=[])
    parser.add_argument("--force-rerun", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.defenses:
        manifest["defenses"] = [str(item) for item in args.defenses]
    args.out_root = args.out_root.resolve()
    args.out_root.mkdir(parents=True, exist_ok=True)
    (args.out_root / "split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    env = configure_env()
    for defense in manifest["defenses"]:
        for suite, split in manifest["suites"].items():
            run_benchmark(
                out_root=args.out_root,
                env=env,
                defense=str(defense),
                suite=str(suite),
                with_attack=False,
                force_rerun=args.force_rerun,
                user_tasks=[str(item) for item in split["user_tasks"]],
                injection_tasks=[str(item) for item in split["injection_tasks"]],
            )
            run_benchmark(
                out_root=args.out_root,
                env=env,
                defense=str(defense),
                suite=str(suite),
                with_attack=True,
                force_rerun=args.force_rerun,
                user_tasks=[str(item) for item in split["user_tasks"]],
                injection_tasks=[str(item) for item in split["injection_tasks"]],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
