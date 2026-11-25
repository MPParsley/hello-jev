"""Demo 1 - hello world for OpenJev, an open-weights (MIT) JEV-style model.

OpenJev (https://huggingface.co/AlexWortega/openjev) does not generate text.
It is a 3-way NLI cross-encoder: it reads a (premise, hypothesis) pair and
returns probabilities for entailment / neutral / contradiction in one pass.

The script runs a few "hello world" examples plus a small rerank demo and
writes everything to site/results.json for the GitHub Pages site.
"""

import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from openjev import REPO_ID, OpenJev

OUT = Path(os.environ.get("OUT_FILE", "site/results.json"))

EXAMPLES = [
    ("Hello world! This program prints a greeting to the screen.",
     "The program says hello."),
    ("Hello world! This program prints a greeting to the screen.",
     "The program deletes all files on the disk."),
    ("Hello world! This program prints a greeting to the screen.",
     "The program was written in Python."),
    ("The GitHub Actions runner downloaded the model and ran it on a CPU.",
     "No GPU was needed to run the model."),
    ("It is raining heavily in Brussels this morning.",
     "The streets in Brussels are dry."),
    ("Maarten booked a train ticket from Ghent to Antwerp for Monday.",
     "Someone is travelling on Monday."),
]

RERANK_QUESTION = "Which statement best describes a 'hello world' program?"
RERANK_PREMISE = ("A 'hello world' program is the simplest possible program: "
                  "it only outputs the text 'Hello, world!' and is used to "
                  "check that a toolchain works.")
RERANK_OPTIONS = [
    "It is a minimal program used to verify a setup.",
    "It is a large enterprise application.",
    "It trains a neural network.",
    "It prints a short greeting.",
]


def main() -> int:
    result = {
        "model": REPO_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runner": {"python": sys.version.split()[0], "platform": platform.platform()},
        "run_url": os.environ.get("RUN_URL"),
        "status": "ok",
    }
    try:
        jev = OpenJev()
        info = dict(jev.info)
        result["runner"]["transformers"] = info.pop("transformers")
        result["runner"]["torch"] = info.pop("torch")
        result.update(info)

        t0 = time.time()
        preds = jev.classify(EXAMPLES)
        result["examples"] = [
            {"premise": p, "hypothesis": h, **pred}
            for (p, h), pred in zip(EXAMPLES, preds)
        ]
        opts = jev.classify([(RERANK_PREMISE, o) for o in RERANK_OPTIONS])
        ranked = sorted(
            ({"option": o, "entailment": r["scores"].get("entailment", 0.0)}
             for o, r in zip(RERANK_OPTIONS, opts)),
            key=lambda x: -x["entailment"])
        result["rerank"] = {"question": RERANK_QUESTION,
                            "premise": RERANK_PREMISE, "ranked": ranked}
        result["inference_seconds"] = round(time.time() - t0, 2)

        for e in result["examples"]:
            print(f"[{e['label']:>13}] {e['hypothesis']}")
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
