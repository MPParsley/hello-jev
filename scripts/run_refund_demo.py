"""Demo 2 - judgments by OpenJev, decisions by code.

For each support ticket:
  1. OpenJev answers each atomic question in refund_policy.JUDGMENTS
     independently (ticket = premise, question = hypothesis).
  2. refund_policy.evaluate() combines those probabilities with facts from
     the order system using deterministic rules and explicit thresholds.
  3. Judgments, rule trace and decision are written to site/refund.json.

Set FAKE_JUDGMENTS=1 to skip the model and use canned probabilities
(handy for working on the page or the policy without downloading weights).
"""

import json
import os
import sys
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from refund_policy import JUDGMENTS, Facts, describe, evaluate

OUT = Path(os.environ.get("OUT_FILE", "site/refund.json"))

TICKETS = [
    {"id": "T1",
     "text": "Hi, the phone case I ordered doesn't fit my phone at all. "
             "Can I please get my money back?",
     "facts": Facts(14.99, 5, 0)},
    {"id": "T2",
     "text": "The espresso machine stopped working after two weeks. "
             "I want a full refund.",
     "facts": Facts(189.00, 14, 0)},
    {"id": "T3",
     "text": "Where is my parcel? The tracking page hasn't updated for four days.",
     "facts": Facts(39.95, 0, 0)},
    {"id": "T4",
     "text": "This is the third time you sent the wrong size. Refund me today "
             "or my lawyer will take you to court.",
     "facts": Facts(22.00, 6, 1)},
    {"id": "T5",
     "text": "My headphones broke after eight months, the left side is completely "
             "dead. I would like my money back.",
     "facts": Facts(24.50, 240, 0)},
    {"id": "T6",
     "text": "I changed my mind about the book I bought, can I return it for a refund?",
     "facts": Facts(12.00, 45, 0)},
    {"id": "T7",
     "text": "I'm not sure I like the colour of the sweater. What are my options?",
     "facts": Facts(19.99, 3, 0)},
]

# Plausible values for FAKE_JUDGMENTS=1 only; the real run uses the model.
FAKE = {
    "T1": (0.98, 0.05, 0.01), "T2": (0.99, 0.97, 0.01), "T3": (0.02, 0.03, 0.01),
    "T4": (0.99, 0.10, 0.95), "T5": (0.97, 0.96, 0.01), "T6": (0.95, 0.02, 0.01),
    "T7": (0.40, 0.02, 0.01),
}


def main() -> int:
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_url": os.environ.get("RUN_URL"),
        "policy": describe(),
        "status": "ok",
    }
    try:
        ids = list(JUDGMENTS)
        if os.environ.get("FAKE_JUDGMENTS"):
            result["model"] = "FAKE_JUDGMENTS (geen model)"
            scored = {t["id"]: [{"scores": {"entailment": p}} for p in FAKE[t["id"]]]
                      for t in TICKETS}
        else:
            from openjev import OpenJev
            jev = OpenJev()
            result.update({k: jev.info[k] for k in
                           ("model", "checkpoint", "parameters", "load_seconds")})
            t0 = time.time()
            # One batch: every (ticket, question) pair is an independent judgment.
            pairs = [(t["text"], JUDGMENTS[i]) for t in TICKETS for i in ids]
            preds = jev.classify(pairs)
            scored = {t["id"]: preds[n * len(ids):(n + 1) * len(ids)]
                      for n, t in enumerate(TICKETS)}
            result["inference_seconds"] = round(time.time() - t0, 2)

        result["tickets"] = []
        for t in TICKETS:
            judgments = {i: {"question": JUDGMENTS[i],
                             "p": s["scores"].get("entailment", 0.0),
                             "scores": s["scores"]}
                         for i, s in zip(ids, scored[t["id"]])}
            decision = evaluate({i: v["p"] for i, v in judgments.items()}, t["facts"])
            result["tickets"].append({"id": t["id"], "text": t["text"],
                                      "facts": asdict(t["facts"]),
                                      "judgments": judgments, **decision})
            print(f"{t['id']}: {decision['outcome']:<14} via {decision['decided_by']}  "
                  + "  ".join(f"{i}={v['p']:.2f}" for i, v in judgments.items()))
    except Exception as exc:  # keep the Pages site alive and show the error
        traceback.print_exc()
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
