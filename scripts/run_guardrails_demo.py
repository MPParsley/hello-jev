"""Demo 3 - Jev judges, Python decides, OPA checks.

Scenario: the business raised the automatic-refund limit from €25 to €50
(policy v2). Risk/compliance keeps independent guardrails in OPA
(policy/guardrails.rego). For each ticket:
  1. reuse the OpenJev judgments from demo 2 (site/refund.json),
  2. let business policy v2 propose a decision,
  3. ask OPA whether that decision may be carried out; any deny turns it
     into a human review.
Writes site/guardrails.json.
"""

import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from refund_policy import OUTCOMES, Facts, evaluate

ROOT = Path(__file__).resolve().parents[1]
IN = Path(os.environ.get("IN_FILE", ROOT / "site/refund.json"))
OUT = Path(os.environ.get("OUT_FILE", ROOT / "site/guardrails.json"))
OPA = os.environ.get("OPA_BIN", "opa")
REGO = ROOT / "policy/guardrails.rego"
POLICY_V2_MAX_EUR = 50.00


def opa_check(inp: dict) -> dict:
    out = subprocess.run(
        [OPA, "eval", "--format", "json", "--stdin-input", "-d", str(REGO),
         "data.refund.guardrails.result"],
        input=json.dumps(inp), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)["result"][0]["expressions"][0]["value"]


def main() -> int:
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_url": os.environ.get("RUN_URL"),
        "policy_version": "v2",
        "policy_v2_max_eur": POLICY_V2_MAX_EUR,
        "rego": REGO.read_text(),
        "status": "ok",
    }
    try:
        demo2 = json.loads(IN.read_text())
        if demo2.get("status") != "ok":
            raise RuntimeError(f"demo 2 failed: {demo2.get('error')}")
        model = {"repo": demo2.get("model"), "checkpoint": demo2.get("checkpoint")}
        result.update(model=model["repo"], checkpoint=model["checkpoint"])
        result["opa_version"] = subprocess.run(
            [OPA, "version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0].removeprefix("Version: ")

        result["tickets"] = []
        for t in demo2["tickets"]:
            judgments = {k: v["p"] for k, v in t["judgments"].items()}
            proposed = evaluate(judgments, Facts(**t["facts"]),
                                auto_refund_max_eur=POLICY_V2_MAX_EUR)
            verdict = opa_check({
                "model": model,
                "judgments": judgments,
                "facts": t["facts"],
                "decision": {"outcome": proposed["outcome"],
                             "decided_by": proposed["decided_by"],
                             "policy_version": "v2"},
            })
            final = verdict["final_outcome"]
            result["tickets"].append({
                "id": t["id"], "text": t["text"], "facts": t["facts"],
                "judgments": judgments,
                "proposed": proposed["outcome"],
                "proposed_label": proposed["outcome_label"],
                "proposed_by": proposed["decided_by"],
                "v1_outcome": t["outcome"],
                "allow": verdict["allow"], "deny": verdict["deny"],
                "final": final, "final_label": OUTCOMES[final],
            })
            print(f"{t['id']}: {proposed['outcome']:<14} -> "
                  f"{'ALLOW' if verdict['allow'] else 'DENY '} -> {final:<14} "
                  + "; ".join(verdict["deny"]))
    except Exception as exc:  # keep the Pages site alive and show the error
        traceback.print_exc()
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr, file=sys.stderr)
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
