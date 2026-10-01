"""Run the v14 frozen mapper protocol with Qwen-Max only.

Gold labels are never sent to the endpoint.  The returned text is parsed through
the same deterministic parser/canonicalizer/compiler used at execution time.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

from clafr.mapper_evaluation import score
from clafr.policy_mapper import MapperAbstention, parse_mapper_response
from dafr_mapper import HandoffMapper, MapperContext


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/mapper_eval_zh_v14_frozen.jsonl"
OUT = ROOT / "results/summaries/mapper_handoff_llm_v1"
CFG = Path("/Users/haomin/Desktop/code/distill/playground-batch-annotate/platform.env")
MODEL = "qwen-max"


def read_cfg():
    cfg = {}
    for line in CFG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            cfg[key] = value.strip().strip('"').strip("'")
    return cfg


def public_case(case):
    return {k: case[k] for k in ("id", "tool_name", "fields", "effect_class", "field_descriptions", "policy")}


def call(case, cfg):
    body = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": 2200,
        "stream": False,
        "messages": HandoffMapper().llm_messages(
            MapperContext(case["tool_name"], tuple(case["fields"]), case.get("effect_class"),
                          case.get("field_descriptions", {}), case["policy"]),
            case.get("candidate_call", {}),
        ),
        "app": cfg["APP_NAME"],
        "quota_id": cfg["QUOTA_ID"],
        "user_id": cfg["USER_ID"],
        "access_key": cfg["ACCESS_KEY"],
    }
    request = Request(
        cfg["API_BASE_URL"].rstrip("/") + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer placeholder"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = read_cfg()
    cases = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    for case in cases:
        public = public_case(case)
        row = {
            "id": case["id"],
            "model": MODEL,
            "input_sha256": hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "gold_sha256": hashlib.sha256(json.dumps(case["gold"], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        }
        start = time.time()
        try:
            response = call(case, cfg)
            content = response["choices"][0]["message"]["content"]
            row["raw_content"] = content
            row["usage"] = response.get("usage")
            try:
                ir = parse_mapper_response(
                    content,
                    case["tool_name"],
                    case["fields"],
                    field_descriptions=case.get("field_descriptions"),
                    effect_class=case.get("effect_class"),
                )
                row.update({"backend_compilable": True, "ir": ir.to_dict()})
            except MapperAbstention as exc:
                row.update({"backend_compilable": False, "status": "abstain", "error": str(exc)[:240]})
            except Exception as exc:
                row.update({"backend_compilable": False, "status": "invalid", "error": f"{type(exc).__name__}: {exc}"[:240]})
        except Exception as exc:
            row.update({"backend_compilable": False, "status": "api_error", "error": f"{type(exc).__name__}: {exc}"[:240]})
        row["elapsed_sec"] = round(time.time() - start, 3)
        if row.get("backend_compilable"):
            row["score"] = score(case, row)
        else:
            row["score"] = score(case, {"backend_compilable": False})
        rows.append(row)
        (OUT / "results.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
        print(json.dumps({"id": row["id"], "status": row.get("status", "ok"), "semantic_exact": row["score"].get("semantic_exact"), "sec": row["elapsed_sec"]}, ensure_ascii=False), flush=True)

    nonamb = [x for x in rows if x["id"] and next(c for c in cases if c["id"] == x["id"])["gold"].get("status") != "abstain"]
    amb = [x for x in rows if next(c for c in cases if c["id"] == x["id"])["gold"].get("status") == "abstain"]
    summary = {
        "model": MODEL,
        "cases": len(rows),
        "nonambiguous": len(nonamb),
        "compile_n": sum(bool(x.get("backend_compilable")) for x in rows),
        "semantic_exact_n": sum(bool(x["score"].get("semantic_exact")) for x in rows),
        "nonambiguous_exact_n": sum(bool(x["score"].get("semantic_exact")) for x in nonamb),
        "ambiguous_n": len(amb),
        "ambiguous_abstain_n": sum(not x.get("backend_compilable") for x in amb),
        "underconstrained_n": sum(bool(x["score"].get("underconstrained")) for x in nonamb if x.get("backend_compilable")),
        "overconstrained_n": sum(bool(x["score"].get("overconstrained")) for x in nonamb if x.get("backend_compilable")),
        "mean_latency_sec": sum(x["elapsed_sec"] for x in rows) / max(1, len(rows)),
        "protocol": "gold withheld; Qwen-Max; train-free handoff prompt; shared parser/canonicalizer/compiler/scorer; v14 frozen",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
