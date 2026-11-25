# hello-jev

Een hello world-demo van een open-weights JEV-model:
[OpenJev](https://huggingface.co/AlexWortega/openjev) (MIT), een niet-generatief
NLI-cross-encoder op basis van Qwen3.5. Het model leest een (premisse, hypothese)-paar
en geeft in één pass de kansen op **entailment / neutral / contradiction**.

## Demo 1 · Hello world (`site/index.html`)

`scripts/run_openjev.py` downloadt het kleinste checkpoint, classificeert een paar voorbeelden,
doet een kleine rerank-demo en schrijft `site/results.json`. Dit toont wat een *judgment model* doet.

## Demo 2 · Jev oordeelt, code beslist (`site/refund.html`)

Naar [“Don’t call it a decision model”](https://typesafe.ai/blog/dont-call-it-a-decision-model):
AI als probabilistische component binnen een deterministisch systeem.

| Laag | Bestand | Verantwoordelijkheid |
|---|---|---|
| Oordelen | `scripts/run_refund_demo.py` + OpenJev | Atomische vragen per ticket (*wil de klant zijn geld terug?*, *is het product defect?*, *dreigt de klant met juridische stappen?*), elk apart beoordeeld als kans op entailment. |
| Beslissing | `scripts/refund_policy.py` | Pure Python, geen AI-imports. Geordende regels met expliciete drempels (geen argmax) combineren de oordelen met feiten uit het ordersysteem (bedrag ≤ €25, retourtermijn, garantie, aantal eerdere terugbetalingen). |
| Tests | `tests/test_refund_policy.py` | De policy wordt getest zonder model. |
| Trace | `site/refund.json` | Per ticket: de oordelen, elke regel (voldaan / niet voldaan / niet bereikt) en de regel die besliste. |

Een nieuw beslissingspad is een nieuwe regel in `refund_policy.py`; een nieuwe vraag aan het model is een
regel in `JUDGMENTS`. Dezelfde input/output (oordelen + feiten → beslissing + trace) kan ook door een
policy engine zoals OPA worden afgehandeld.

## Workflow

`.github/workflows/demo.yml` test de policy, draait beide demo's op een CPU-runner (bij een push naar
`main`, handmatig en wekelijks) en publiceert `site/` op GitHub Pages.

## Eenmalige setup

**Settings → Pages → Build and deployment → Source: GitHub Actions.**
Start daarna de workflow (Actions → *Hello JEV* → *Run workflow*) of push naar `main`.

## Lokaal draaien

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python -m unittest discover -s tests   # policy-tests, zonder model
python scripts/run_openjev.py   # schrijft site/results.json
python scripts/run_refund_demo.py   # schrijft site/refund.json (FAKE_JUDGMENTS=1: zonder model)
python -m http.server -d site    # open http://localhost:8000
```

Een ander checkpoint kiezen: `OPENJEV_CHECKPOINT=<subfolder> python scripts/run_openjev.py`.
