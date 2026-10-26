# hello-jev

Een hello world-demo van een open-weights JEV-model:
[OpenJev](https://huggingface.co/AlexWortega/openjev) (MIT), een niet-generatief
NLI-cross-encoder op basis van Qwen3.5. Het model leest een (premisse, hypothese)-paar
en geeft in één pass de kansen op **entailment / neutral / contradiction**.

- `scripts/run_openjev.py` downloadt het kleinste checkpoint, classificeert een paar voorbeelden,
  doet een kleine rerank-demo en schrijft `site/results.json`.
- `.github/workflows/demo.yml` voert het script uit op een CPU-runner (bij een push naar `main`,
  handmatig en wekelijks) en publiceert `site/` op GitHub Pages.
- `site/index.html` visualiseert de resultaten.

## Eenmalige setup

**Settings → Pages → Build and deployment → Source: GitHub Actions.**
Start daarna de workflow (Actions → *Hello JEV* → *Run workflow*) of push naar `main`.

## Lokaal draaien

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python scripts/run_openjev.py   # schrijft site/results.json
python -m http.server -d site    # open http://localhost:8000
```

Een ander checkpoint kiezen: `OPENJEV_CHECKPOINT=<subfolder> python scripts/run_openjev.py`.
