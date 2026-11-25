# hello-jev

Een hello world-demo van een open-weights JEV-model:
[OpenJev](https://huggingface.co/AlexWortega/openjev) (MIT), een niet-generatief
NLI-cross-encoder op basis van Qwen3.5. Het model leest een (premisse, hypothese)-paar
en geeft in één pass de kansen op **entailment / neutral / contradiction**.

## Demo 1 · Hello Jev: hoe werkt een judgment model? (`site/index.html`)

`scripts/run_openjev.py` downloadt het kleinste checkpoint, classificeert een paar voorbeelden,
doet een kleine rerank-demo en schrijft `site/results.json`. Dit toont wat een *judgment model* doet.

## Demo 2 · Jev + Python: hoe worden beoordelingen beslissingen? (`site/refund.html`)

Naar [“Don’t call it a decision model”](https://typesafe.ai/blog/dont-call-it-a-decision-model):
AI als probabilistische component binnen een deterministisch systeem.

| Laag | Bestand | Verantwoordelijkheid |
|---|---|---|
| Oordelen | `scripts/run_refund_demo.py` + OpenJev | Atomische vragen per ticket (*wil de klant zijn geld terug?*, *is het product defect?*, *dreigt de klant met juridische stappen?*), elk apart beoordeeld als kans op entailment. |
| Beslissing | `scripts/refund_policy.py` | Pure Python, geen AI-imports. Geordende regels met expliciete drempels (geen argmax) combineren de oordelen met feiten uit het ordersysteem (bedrag ≤ €25, retourtermijn, garantie, aantal eerdere terugbetalingen). |
| Tests | `tests/test_refund_policy.py` | De policy wordt getest zonder model. |
| Trace | `site/refund.json` | Per ticket: de oordelen, elke regel (voldaan / niet voldaan / niet bereikt) en de regel die besliste. |

De drempel voor `legal_threat` ligt bewust lager (60%) dan voor de andere oordelen (90%): een echte
juridische dreiging missen kost veel meer dan een gewone klacht onterecht naar juridische zaken sturen.

Een nieuw beslissingspad is een nieuwe regel in `refund_policy.py`; een nieuwe vraag aan het model is een
regel in `JUDGMENTS`. Dezelfde input/output (oordelen + feiten → beslissing + trace) kan ook door een
policy engine zoals OPA worden afgehandeld.

## Demo 3 · Jev + Python + OPA: hoe worden AI-ondersteunde beslissingen gecontroleerd? (`site/guardrails.html`)

Scenario: de business verhoogt de grens voor automatische terugbetaling naar €50 (policy v2).
Risk & compliance houdt onafhankelijke guardrails bij in [Open Policy Agent](https://www.openpolicyagent.org/).
OPA herhaalt de businesslogica niet, maar legt grenzen vast die altijd moeten gelden:

| Guardrail | Regel |
|---|---|
| G1 | Nooit automatisch meer dan €25 terugbetalen. |
| G2 | Geen automatische beslissing als `legal_threat` > 30%. |
| G3 | Automatische beslissingen alleen bij een zeker oordeel (`wants_refund` ≥ 90% of ≤ 10%). |
| G4 | Alleen goedgekeurde modelversies mogen automatische beslissingen sturen. |

`scripts/run_guardrails_demo.py` hergebruikt de oordelen van demo 2, laat policy v2 een beslissing voorstellen
en vraagt OPA (`policy/guardrails.rego`, getest in `policy/guardrails_test.rego`) of die mag worden uitgevoerd.
Een weigering wordt een menselijke review.

| Laag | Eigenaar | Verandert |
|---|---|---|
| OpenJev (oordelen) | data/AI-team | bij een nieuw model of een nieuwe vraag |
| Python (businessregels) | business | vaak |
| OPA (guardrails) | risk & compliance | zelden, gedeeld over systemen |

## Workflow

`.github/workflows/demo.yml` test de Python-policy en de Rego-guardrails, draait de drie demo's op een CPU-runner (bij een push naar
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
opa test policy/ -v                  # guardrail-tests
python scripts/run_guardrails_demo.py   # schrijft site/guardrails.json (vereist opa in PATH of OPA_BIN)
python -m http.server -d site    # open http://localhost:8000
```

Een ander checkpoint kiezen: `OPENJEV_CHECKPOINT=<subfolder> python scripts/run_openjev.py`.
