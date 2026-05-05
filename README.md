# FVSC — Fractal-Vector Semantic Core

Deterministic personal semantic mapping through density matrices.

Records what words mean to a specific person — not what they mean in general.

## How it works

```
text → spaCy → context classifier → recursive tree extractor → density matrices → interactive map
```

Each concept becomes a density matrix operator. Containment, polysemy, and semantic depth — all from linear algebra, no neural networks, no training.

## Quick start

```bash
pip install -r requirements.txt
python -m spacy download ru_core_news_md
cd core
python test_poc.py
```

## Author

Created by **Rein** with the support of **Claude** (Anthropic).
