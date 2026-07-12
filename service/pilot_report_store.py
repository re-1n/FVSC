"""Atomic JSON and Markdown storage for pilot evaluation reports."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


EVALUATION_REPORT_NAME = "heldout-evaluation-latest.json"
EVALUATION_REVIEW_PATH = Path("_fvsc_review") / "FVSC Held-out Evaluation.md"


def atomic_write_text(path: Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def save_evaluation_report(vault: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    json_path = Path(vault) / ".fvsc" / EVALUATION_REPORT_NAME
    json_text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    )
    atomic_write_text(json_path, json_text)

    markdown_path = Path(vault) / EVALUATION_REVIEW_PATH
    atomic_write_text(markdown_path, render_evaluation_markdown(payload))
    return json_path, markdown_path


def load_evaluation_report(vault: Path) -> dict[str, Any] | None:
    path = Path(vault) / ".fvsc" / EVALUATION_REPORT_NAME
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _number(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def render_evaluation_markdown(report: dict[str, Any]) -> str:
    models = report.get("models", {}) if isinstance(report.get("models"), dict) else {}
    lines = [
        "# FVSC Pilot — Held-out Evaluation",
        "",
        f"Generated: {report.get('generated_at', '—')}",
        f"Verdict: **{report.get('verdict', 'unknown')}**",
        "",
        "> Этот тест использует ранние заметки как train, поздние как held-out test. "
        "Он проверяет предсказательную различимость, но не психологическую валидность.",
        "",
        "## Data",
        "",
        f"- Train documents: {report.get('train_documents', 0)}",
        f"- Test documents: {report.get('test_documents', 0)}",
        f"- Evaluated test documents: {report.get('evaluated_test_documents', 0)}",
        f"- Known-positive coverage: {_number(report.get('known_positive_coverage'))}",
        f"- Positive pairs: {report.get('positive_pairs_known', 0)} / {report.get('positive_pairs_total', 0)}",
        "",
        "## Models",
        "",
        "| Model | AUC | Average precision | Comparisons |",
        "|---|---:|---:|---:|",
    ]
    labels = {
        "fvsc_shape": "FVSC shape",
        "direct_graph": "Direct graph",
        "trace_mass": "Trace mass",
        "random": "Random",
    }
    for key in ("fvsc_shape", "direct_graph", "trace_mass", "random"):
        model = models.get(key, {}) if isinstance(models.get(key), dict) else {}
        lines.append(
            f"| {labels[key]} | {_number(model.get('auc'))} | "
            f"{_number(model.get('average_precision'))} | "
            f"{model.get('pairwise_comparisons', 0)} |"
        )
    ci = report.get("paired_bootstrap_ci95") or [None, None]
    if not isinstance(ci, list) or len(ci) != 2:
        ci = [None, None]
    lines.extend([
        "",
        "## Comparison",
        "",
        f"- Best baseline: `{report.get('best_baseline', '—')}`",
        f"- FVSC AUC delta: {_number(report.get('fvsc_auc_delta_vs_best_baseline'), 4)}",
        f"- Paired bootstrap CI95: [{_number(ci[0], 4)}, {_number(ci[1], 4)}]",
        "",
        "## Interpretation",
        "",
    ])
    verdict = report.get("verdict")
    interpretations = {
        "insufficient_data": "Пока недостаточно held-out данных для вывода.",
        "promising_added_value": "FVSC превзошёл лучший baseline по заранее заданным критериям; нужен более длинный слепой пилот.",
        "not_predictive": "Текущая модель не показывает приемлемого predictive signal.",
        "no_demonstrated_added_value": "Predictive signal может быть, но уникальное преимущество над простыми baseline не показано.",
    }
    lines.append(interpretations.get(verdict, "Вердикт не распознан; проверьте JSON-отчёт."))
    lines.extend([
        "",
        "## Limitations",
        "",
    ])
    for limitation in report.get("limitations", []):
        lines.append(f"- {limitation}")
    lines.extend([
        "",
        "## User notes",
        "",
        "- ",
        "",
    ])
    return "\n".join(lines)
