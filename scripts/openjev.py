"""Shared OpenJev loading and scoring, used by both demos."""

import os
import re
import time

REPO_ID = os.environ.get("OPENJEV_REPO", "AlexWortega/openjev")
CHECKPOINT = os.environ.get("OPENJEV_CHECKPOINT", "")  # empty = auto (smallest)


def size_key(name: str) -> float:
    """Sort checkpoints by parameter count parsed from the folder name."""
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


class OpenJev:
    """Thin wrapper: (premise, hypothesis) pairs in, label probabilities out."""

    def __init__(self):
        import torch
        import transformers
        from transformers import (AutoModelForSequenceClassification,
                                  AutoTokenizer)

        self.torch = torch
        sub = pick_checkpoint()
        kw = {"subfolder": sub} if sub else {}
        t0 = time.time()
        self.tok = AutoTokenizer.from_pretrained(REPO_ID, **kw)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            REPO_ID, dtype=torch.float32, **kw).eval()
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.model.config.pad_token_id = self.tok.pad_token_id

        id2label = {int(k): v.lower() for k, v in self.model.config.id2label.items()}
        if all(v.startswith("label_") for v in id2label.values()):
            # Label order documented in the OpenJev model card.
            id2label = {0: "contradiction", 1: "entailment", 2: "neutral"}
        self.id2label = id2label
        self.info = {
            "model": REPO_ID,
            "checkpoint": sub or "<root>",
            "parameters": sum(p.numel() for p in self.model.parameters()),
            "load_seconds": round(time.time() - t0, 1),
            "labels": [id2label[i] for i in sorted(id2label)],
            "transformers": transformers.__version__,
            "torch": torch.__version__,
        }

    def classify(self, pairs):
        """Return [{'scores': {label: p}, 'label': argmax}] for each pair."""
        enc = self.tok([p for p, _ in pairs], [h for _, h in pairs],
                       return_tensors="pt", padding=True, truncation=True,
                       max_length=512)
        with self.torch.no_grad():
            probs = self.model(**enc).logits.float().softmax(-1)
        out = []
        for row in probs.tolist():
            scores = {self.id2label[i]: round(p, 4) for i, p in enumerate(row)}
            out.append({"scores": scores, "label": max(scores, key=scores.get)})
        return out
