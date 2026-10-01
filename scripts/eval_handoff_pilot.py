"""Offline handoff pilot: replays frozen v14 responses through the new interface."""
from __future__ import annotations

import json
from pathlib import Path

from clafr.mapper_evaluation import score
from dafr_mapper import HandoffMapper, MapperContext

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/mapper_eval_zh_v14_frozen.jsonl"
RAW = ROOT / "results/summaries/mapper_eval_zh_v14_qwen_test/results.jsonl"


def main() -> None:
    cases = {json.loads(x)["id"]: json.loads(x) for x in DATA.read_text().splitlines() if x.strip()}
    rows = [json.loads(x) for x in RAW.read_text().splitlines() if x.strip()]
    mapper = HandoffMapper()
    exact = compiled = abstain = 0
    fingerprints = {}
    for row in rows:
        case = cases[row["id"]]
        context = MapperContext(case["tool_name"], tuple(case["fields"]), case.get("effect_class"), case.get("field_descriptions", {}), case["policy"])
        usable = False
        if row.get("raw_content"):
            try:
                output = mapper.map_response(row["raw_content"], context)
                usable = mapper.check_region_membership(output)
                row = {"backend_compilable": True, "ir": output.ir.to_dict()}
                fingerprints[case["id"]] = output.region_fingerprint
            except Exception:
                row = {"backend_compilable": False}
        else:
            row = {"backend_compilable": False}
        compiled += int(usable)
        abstain += int(not usable)
        exact += int(score(case, row)["semantic_exact"])
    print(json.dumps({"cases": len(rows), "compiled": compiled, "abstain": abstain, "semantic_exact": exact,
                      "candidate_independent_regions": len(fingerprints) == compiled}, ensure_ascii=False))


if __name__ == "__main__":
    main()
