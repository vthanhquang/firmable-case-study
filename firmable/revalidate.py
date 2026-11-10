"""Re-run the CURRENT deterministic gates over the APPROVED configs (no model calls).

Gates improve over time (rare-value held-out rows, placeholder detection). An approved config must be
re-checked whenever its gates change; this is the same check a scheduled drift job would run.
"""
from __future__ import annotations

import json

from .agent.workspace import Workspace
from .extract import load_config
from .mapping.validate import holdout_issues, static_issues
from .paths import OUT_EVAL, OUT_MAPPINGS
from .sources.select import load_manifest


def run() -> dict:
    man = load_manifest()
    out = {}
    for p in sorted(OUT_MAPPINGS.glob("*.json")):
        sid = p.stem
        cfg, doc = load_config(sid)
        ws = Workspace(man[sid])
        disc, hold, cols, _ = ws.pool(cfg.reader)
        issues, rep = holdout_issues(cfg, disc, hold, man[sid])
        issues = static_issues(cfg, set(cols)) + issues
        out[sid] = {"config_digest": cfg.digest(), "holdout_records": len(hold),
                    "rare_value_records": ws.rare_holdout(cfg.reader),
                    "errors": [i for i in issues if i["severity"] == "error"],
                    "warnings": [i["code"] + ":" + str(i.get("target")) for i in issues if i["severity"] == "warning"]}
        print(sid, "errors:", [(i["code"], i.get("target")) for i in out[sid]["errors"]], flush=True)
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    (OUT_EVAL / "revalidation_current_gates.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out


if __name__ == "__main__":
    run()
