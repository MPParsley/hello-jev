"""Hello world demo for OpenJev, an open-weights (MIT) JEV-style model.

OpenJev (https://huggingface.co/AlexWortega/openjev) does not generate text.
It is a 3-way NLI cross-encoder: it reads a (premise, hypothesis) pair and
returns probabilities for entailment / neutral / contradiction in one pass.

The script picks the smallest checkpoint in the repo (CPU-friendly for GitHub
Actions), runs a few "hello world" examples plus a small rerank demo and
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

REPO_ID = os.environ.get("OPENJEV_REPO", "AlexWortega/openjev")
CHECKPOINT = os.environ.get("OPENJEV_CHECKPOINT", "")  # empty = auto (smallest)
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


def size_key(name: str) -> float:
    """Sort checkpoints by parameter count parsed from the folder name."""
    import re
    m = re.search(r"(\d+(?:\.\d+)?)\s*b", name.lower())
    return float(m.group(1)) if m else 1e9


def pick_checkpoint() -> str:
    """Return the subfolder ('' = repo root) holding the smallest checkpoint."""
    if CHECKPOINT:
        return CHECKPOINT
    from huggingface_hub import list_repo_files
    files = list_repo_files(REPO_ID)
    folders = sorted({f.rsplit("/", 1)[0] if "/" in f else ""
                      for f in files if f.endswith("config.json")
                      and not f.endswith(("tokenizer_config.json",
                                          "generation_config.json"))})
    print("Checkpoints found:", folders or ["<root>"])
    candidates = [f for f in folders if f] or [""]
    # Smallest model size; among those, the highest (newest) version name.
    smallest = min(size_key(c) for c in candidates)
    return max(c for c in candidates if size_key(c) == smallest)


def main() -> int:
    result = {
        "model": REPO_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runner": {"python": sys.version.split()[0], "platform": platform.platform()},
        "run_url": os.environ.get("RUN_URL"),
        "status": "ok",
    }
    try:
        import torch
        from transformers import (AutoModelForSequenceClassification,
                                  AutoTokenizer)
        import transformers

        sub = pick_checkpoint()
        result["checkpoint"] = sub or "<root>"
        result["runner"]["transformers"] = transformers.__version__
        result["runner"]["torch"] = torch.__version__
        kw = {"subfolder": sub} if sub else {}

        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(REPO_ID, **kw)
        model = AutoModelForSequenceClassification.from_pretrained(
            REPO_ID, torch_dtype=torch.float32, **kw).eval()
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        model.config.pad_token_id = tok.pad_token_id
        result["load_seconds"] = round(time.time() - t0, 1)
        result["parameters"] = sum(p.numel() for p in model.parameters())

        id2label = {int(k): v.lower() for k, v in model.config.id2label.items()}
        if all(v.startswith("label_") for v in id2label.values()):
            # Label order documented in the OpenJev model card.
            id2label = {0: "contradiction", 1: "entailment", 2: "neutral"}
        result["labels"] = [id2label[i] for i in sorted(id2label)]

        def classify(pairs):
            enc = tok([p for p, _ in pairs], [h for _, h in pairs],
                      return_tensors="pt", padding=True, truncation=True,
                      max_length=512)
            with torch.no_grad():
                probs = model(**enc).logits.float().softmax(-1)
            out = []
            for row in probs.tolist():
                scores = {id2label[i]: round(p, 4) for i, p in enumerate(row)}
                out.append({"scores": scores,
                            "label": max(scores, key=scores.get)})
            return out

        t0 = time.time()
        preds = classify(EXAMPLES)
        result["examples"] = [
            {"premise": p, "hypothesis": h, **pred}
            for (p, h), pred in zip(EXAMPLES, preds)
        ]
        opts = classify([(RERANK_PREMISE, o) for o in RERANK_OPTIONS])
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
