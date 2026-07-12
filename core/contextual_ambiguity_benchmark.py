"""Contextual ambiguity bakeoff for candidate FVSC semantic backends.

The evaluator follows the official WiC train/dev/test split. Representation fitting
uses train contexts only, thresholds and family selection use dev labels, and the
test split is evaluated once. Raw third-party data remain outside Git.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

import numpy as np

from .text_parser_agnostic import DEFAULT_STOPWORDS_RU_EN


BENCHMARK_VERSION = "fvsc-contextual-ambiguity-bakeoff-v1"
WIC_LICENSE = "CC BY-NC 4.0"
WIC_OFFICIAL_URL = "https://pilehvar.github.io/wic/package/WiC_dataset.zip"
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
_EPS = 1e-12
_TOKEN_RE = re.compile(r"[\w'-]+", flags=re.UNICODE)


@dataclass(frozen=True)
class ContextPair:
    split: str
    example_id: str
    target: str
    pos: str
    index1: int
    index2: int
    context1: str
    context2: str
    same_sense: bool

    @property
    def target_key(self) -> str:
        return f"{self.target.casefold()}::{self.pos.upper()}"


@dataclass(frozen=True)
class TargetProfile:
    density: np.ndarray
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    centroids: np.ndarray
    occurrence_count: int


@dataclass(frozen=True)
class ContextFeatureSpace:
    idf: Mapping[str, float]
    dim: int
    target_profiles: Mapping[str, TargetProfile]
    global_profile: TargetProfile
    train_target_keys: frozenset[str]


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            target = (destination / member.filename).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValueError("dataset archive contains a path traversal entry") from exc
        handle.extractall(destination)


def fetch_wic_package(
    *,
    output_dir: Path,
    url: str = WIC_OFFICIAL_URL,
    timeout: float = 60.0,
) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "pilehvar.github.io":
        raise ValueError("WiC download must use the official HTTPS host")
    output_dir.mkdir(parents=True, exist_ok=True)
    request = Request(
        url,
        headers={
            "User-Agent": "FVSC-contextual-ambiguity-benchmark/1.0 evaluation-only",
            "Accept": "application/zip",
        },
    )
    chunks: list[bytes] = []
    total = 0
    with urlopen(request, timeout=timeout) as response:  # nosec B310: fixed host
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise ValueError("WiC package exceeds the download limit")
            chunks.append(chunk)
    data = b"".join(chunks)
    archive = output_dir / "WiC_dataset.zip"
    archive.write_bytes(data)
    extracted = output_dir / "dataset"
    if extracted.exists():
        shutil.rmtree(extracted)
    extracted.mkdir(parents=True)
    _safe_extract_zip(archive, extracted)
    root = locate_wic_root(extracted)
    metadata = {
        "dataset": "WiC 1.0",
        "source_url": url,
        "license": WIC_LICENSE,
        "package_sha256": hashlib.sha256(data).hexdigest(),
        "package_bytes": len(data),
        "dataset_root": str(root),
        "usage_purpose": "evaluation_only_no_model_training",
    }
    (output_dir / "wic-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return metadata


def _find_split_file(root: Path, split: str, kind: str) -> Path | None:
    for candidate in (
        root / split / f"{split}.{kind}.txt",
        root / f"{split}.{kind}.txt",
    ):
        if candidate.exists():
            return candidate
    matches = sorted(root.rglob(f"{split}.{kind}.txt"))
    return matches[0] if matches else None


def locate_wic_root(path: Path) -> Path:
    candidates = [path, *sorted(item for item in path.rglob("*") if item.is_dir())]
    for candidate in candidates:
        if all(
            _find_split_file(candidate, split, kind) is not None
            for split in ("train", "dev", "test")
            for kind in ("data", "gold")
        ):
            return candidate
    raise FileNotFoundError("could not locate WiC train/dev/test files")


def load_wic_split(root: Path, split: str) -> tuple[ContextPair, ...]:
    split = split.casefold()
    if split not in {"train", "dev", "test"}:
        raise ValueError("split must be train, dev or test")
    data_path = _find_split_file(root, split, "data")
    gold_path = _find_split_file(root, split, "gold")
    if data_path is None or gold_path is None:
        raise FileNotFoundError(f"missing WiC {split} files")
    data_lines = data_path.read_text(encoding="utf-8").splitlines()
    gold_lines = gold_path.read_text(encoding="utf-8").splitlines()
    if len(data_lines) != len(gold_lines):
        raise ValueError(f"WiC {split} data/gold line counts differ")

    result: list[ContextPair] = []
    for number, (data_line, gold_line) in enumerate(zip(data_lines, gold_lines), 1):
        fields = data_line.split("\t")
        if len(fields) != 5:
            raise ValueError(f"invalid WiC {split} data line {number}")
        target, pos, indexes, context1, context2 = fields
        try:
            first, second = indexes.split("-", 1)
            index1, index2 = int(first), int(second)
        except ValueError as exc:
            raise ValueError(f"invalid WiC indexes at line {number}") from exc
        label = gold_line.strip().upper()
        if label not in {"T", "F"}:
            raise ValueError(f"invalid WiC label at line {number}")
        result.append(
            ContextPair(
                split=split,
                example_id=f"{split}:{number}",
                target=target.strip(),
                pos=pos.strip().upper(),
                index1=index1,
                index2=index2,
                context1=context1.strip(),
                context2=context2.strip(),
                same_sense=label == "T",
            )
        )
    return tuple(result)


def _context_tokens(sentence: str, target_index: int, target: str) -> tuple[str, ...]:
    raw = sentence.split()
    if 0 <= target_index < len(raw):
        raw = [token for index, token in enumerate(raw) if index != target_index]
    stop = set(DEFAULT_STOPWORDS_RU_EN)
    stop.add(target.casefold())
    tokens: list[str] = []
    for item in raw:
        for token in _TOKEN_RE.findall(item.casefold()):
            if len(token) >= 2 and token not in stop and not token.isdigit():
                tokens.append(token)
    return tuple(tokens)


def _occurrences(examples: Iterable[ContextPair]) -> list[tuple[str, tuple[str, ...]]]:
    rows: list[tuple[str, tuple[str, ...]]] = []
    for item in examples:
        rows.append((item.target_key, _context_tokens(item.context1, item.index1, item.target)))
        rows.append((item.target_key, _context_tokens(item.context2, item.index2, item.target)))
    return rows


def _fit_idf(examples: Sequence[ContextPair]) -> dict[str, float]:
    rows = _occurrences(examples)
    document_frequency: Counter[str] = Counter()
    for _target, tokens in rows:
        document_frequency.update(set(tokens))
    count = len(rows)
    return {
        token: math.log((1.0 + count) / (1.0 + frequency)) + 1.0
        for token, frequency in document_frequency.items()
    }


def _sparse_tfidf(tokens: Sequence[str], idf: Mapping[str, float]) -> dict[str, float]:
    weighted = {
        token: float(count) * float(idf.get(token, 1.0))
        for token, count in Counter(tokens).items()
    }
    norm = math.sqrt(sum(value * value for value in weighted.values()))
    return {token: value / norm for token, value in weighted.items()} if norm > _EPS else {}


def _sparse_cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return float(sum(value * right.get(token, 0.0) for token, value in left.items()))


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set, right_set = set(left), set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0


def _hashed_vector(tokens: Sequence[str], idf: Mapping[str, float], dim: int) -> np.ndarray:
    vector = np.zeros(dim, dtype=float)
    for token, count in Counter(tokens).items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "little") % dim
        sign = 1.0 if digest[8] & 1 else -1.0
        vector[index] += sign * count * float(idf.get(token, 1.0))
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > _EPS else vector


def _normalize_density(matrix: np.ndarray) -> np.ndarray:
    matrix = (np.asarray(matrix, dtype=float) + np.asarray(matrix, dtype=float).T) / 2.0
    trace = float(np.trace(matrix))
    if trace <= _EPS:
        return np.eye(matrix.shape[0], dtype=float) / matrix.shape[0]
    return matrix / trace


def _fit_centroids(vectors: Sequence[np.ndarray], key: str, max_facets: int = 4) -> np.ndarray:
    matrix = np.vstack(vectors)
    count = len(matrix)
    k = min(max_facets, max(1, int(round(math.sqrt(count / 2.0)))))
    first = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little") % count
    chosen = [first]
    while len(chosen) < k:
        nearest = np.max(matrix @ matrix[chosen].T, axis=1)
        for index in chosen:
            nearest[index] = np.inf
        candidate = int(np.argmin(nearest))
        if candidate in chosen:
            break
        chosen.append(candidate)
    centroids = np.array(matrix[chosen], copy=True)
    for _ in range(20):
        assignments = np.argmax(matrix @ centroids.T, axis=1)
        updated = []
        for cluster in range(len(centroids)):
            members = matrix[assignments == cluster]
            if not len(members):
                updated.append(centroids[cluster])
                continue
            centroid = np.mean(members, axis=0)
            norm = float(np.linalg.norm(centroid))
            updated.append(centroid / norm if norm > _EPS else centroids[cluster])
        new_centroids = np.vstack(updated)
        if np.allclose(new_centroids, centroids, atol=1e-10):
            return new_centroids
        centroids = new_centroids
    return centroids


def _profile(vectors: Sequence[np.ndarray], key: str, dim: int) -> TargetProfile:
    density = _normalize_density(sum((np.outer(v, v) for v in vectors), np.zeros((dim, dim))))
    values, vectors_matrix = np.linalg.eigh(density)
    order = np.argsort(values)[::-1]
    values = np.maximum(values[order], 0.0)
    vectors_matrix = vectors_matrix[:, order]
    active = values > 1e-10
    values = values[active][:8]
    vectors_matrix = vectors_matrix[:, active][:, :8]
    if not len(values):
        values = np.asarray([1.0])
        vectors_matrix = np.eye(dim, 1)
    values /= max(float(np.sum(values)), _EPS)
    return TargetProfile(
        density=density,
        eigenvalues=values,
        eigenvectors=vectors_matrix,
        centroids=_fit_centroids(vectors, key),
        occurrence_count=len(vectors),
    )


def fit_feature_space(train: Sequence[ContextPair], *, dim: int = 64) -> ContextFeatureSpace:
    if dim < 8:
        raise ValueError("dim must be at least 8")
    idf = _fit_idf(train)
    grouped: dict[str, list[np.ndarray]] = defaultdict(list)
    all_vectors: list[np.ndarray] = []
    for key, tokens in _occurrences(train):
        vector = _hashed_vector(tokens, idf, dim)
        if float(np.linalg.norm(vector)) > _EPS:
            grouped[key].append(vector)
            all_vectors.append(vector)
    if not all_vectors:
        all_vectors = [np.eye(dim)[0]]
    profiles = {key: _profile(rows, key, dim) for key, rows in sorted(grouped.items())}
    return ContextFeatureSpace(
        idf=idf,
        dim=dim,
        target_profiles=profiles,
        global_profile=_profile(all_vectors, "__global__", dim),
        train_target_keys=frozenset(profiles),
    )


def _condition_density(density: np.ndarray, context: np.ndarray, floor: float = 0.15) -> np.ndarray:
    if float(np.linalg.norm(context)) <= _EPS:
        return density
    projector = np.outer(context, context)
    root = math.sqrt(floor) * np.eye(len(context))
    root += (math.sqrt(1.0 + floor) - math.sqrt(floor)) * projector
    return _normalize_density(root @ density @ root)


def _density_overlap(left: np.ndarray, right: np.ndarray) -> float:
    denominator = math.sqrt(
        max(float(np.trace(left @ left)), _EPS)
        * max(float(np.trace(right @ right)), _EPS)
    )
    return float(np.clip(float(np.trace(left @ right)) / denominator, 0.0, 1.0))


def _facet_distribution(profile: TargetProfile, context: np.ndarray) -> np.ndarray:
    weights = profile.eigenvalues * np.square(profile.eigenvectors.T @ context)
    total = float(np.sum(weights))
    return weights / total if total > _EPS else np.full(len(weights), 1.0 / len(weights))


def _centroid_distribution(profile: TargetProfile, context: np.ndarray) -> np.ndarray:
    logits = 5.0 * np.clip(profile.centroids @ context, -1.0, 1.0)
    logits -= np.max(logits)
    weights = np.exp(logits)
    return weights / max(float(np.sum(weights)), _EPS)


def _bhattacharyya(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.clip(np.sum(np.sqrt(left * right)), 0.0, 1.0))


class ContextualRepresentationSuite:
    MODEL_NAMES = (
        "token_jaccard",
        "tfidf_cosine",
        "hashed_context_cosine",
        "explicit_kmeans_facets",
        "density_posterior_overlap",
        "density_eigenfacet_overlap",
        "random",
    )
    DENSITY_MODELS = frozenset({"density_posterior_overlap", "density_eigenfacet_overlap"})

    def __init__(self, feature_space: ContextFeatureSpace) -> None:
        self.feature_space = feature_space

    def score(self, item: ContextPair) -> dict[str, float]:
        tokens1 = _context_tokens(item.context1, item.index1, item.target)
        tokens2 = _context_tokens(item.context2, item.index2, item.target)
        sparse1 = _sparse_tfidf(tokens1, self.feature_space.idf)
        sparse2 = _sparse_tfidf(tokens2, self.feature_space.idf)
        vector1 = _hashed_vector(tokens1, self.feature_space.idf, self.feature_space.dim)
        vector2 = _hashed_vector(tokens2, self.feature_space.idf, self.feature_space.dim)
        profile = self.feature_space.target_profiles.get(item.target_key, self.feature_space.global_profile)
        posterior1 = _condition_density(profile.density, vector1)
        posterior2 = _condition_density(profile.density, vector2)
        random_bytes = hashlib.sha256(item.example_id.encode()).digest()
        return {
            "token_jaccard": _jaccard(tokens1, tokens2),
            "tfidf_cosine": _sparse_cosine(sparse1, sparse2),
            "hashed_context_cosine": float(np.clip(np.dot(vector1, vector2), -1.0, 1.0)),
            "explicit_kmeans_facets": _bhattacharyya(
                _centroid_distribution(profile, vector1),
                _centroid_distribution(profile, vector2),
            ),
            "density_posterior_overlap": _density_overlap(posterior1, posterior2),
            "density_eigenfacet_overlap": _bhattacharyya(
                _facet_distribution(profile, vector1),
                _facet_distribution(profile, vector2),
            ),
            "random": int.from_bytes(random_bytes[:8], "little") / float(2**64 - 1),
        }


def _roc_auc(labels: Sequence[bool], scores: Sequence[float]) -> float:
    positives = [score for label, score in zip(labels, scores) if label]
    negatives = [score for label, score in zip(labels, scores) if not label]
    if not positives or not negatives:
        return 0.5
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            wins += 1.0 if positive > negative + _EPS else 0.5 if abs(positive - negative) <= _EPS else 0.0
    return wins / (len(positives) * len(negatives))


def _classification_metrics(labels: Sequence[bool], scores: Sequence[float], threshold: float) -> dict[str, float | int]:
    predictions = [score >= threshold for score in scores]
    tp = sum(label and prediction for label, prediction in zip(labels, predictions))
    tn = sum((not label) and (not prediction) for label, prediction in zip(labels, predictions))
    fp = sum((not label) and prediction for label, prediction in zip(labels, predictions))
    fn = sum(label and (not prediction) for label, prediction in zip(labels, predictions))
    total = len(labels)
    tpr = tp / (tp + fn) if tp + fn else 0.0
    tnr = tn / (tn + fp) if tn + fp else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * precision * tpr / (precision + tpr) if precision + tpr else 0.0
    return {
        "examples": total,
        "accuracy": (tp + tn) / total if total else 0.0,
        "balanced_accuracy": (tpr + tnr) / 2.0,
        "precision": precision,
        "recall": tpr,
        "f1": f1,
        "roc_auc": _roc_auc(labels, scores),
        "threshold": threshold,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def _choose_threshold(labels: Sequence[bool], scores: Sequence[float]) -> float:
    unique = sorted(set(float(score) for score in scores))
    if not unique:
        return 0.5
    candidates = [unique[0] - 1e-9]
    candidates.extend((left + right) / 2.0 for left, right in zip(unique, unique[1:]))
    candidates.append(unique[-1] + 1e-9)
    return max(
        candidates,
        key=lambda threshold: (
            _classification_metrics(labels, scores, threshold)["balanced_accuracy"],
            _classification_metrics(labels, scores, threshold)["accuracy"],
            -abs(threshold - 0.5),
        ),
    )


def _score_examples(suite: ContextualRepresentationSuite, examples: Sequence[ContextPair]) -> dict[str, list[float]]:
    scores = {name: [] for name in suite.MODEL_NAMES}
    for item in examples:
        values = suite.score(item)
        for name in suite.MODEL_NAMES:
            scores[name].append(float(values[name]))
    return scores


def _paired_accuracy_bootstrap(
    labels: Sequence[bool],
    left_scores: Sequence[float],
    left_threshold: float,
    right_scores: Sequence[float],
    right_threshold: float,
    *,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    if not labels:
        return 0.0, 0.0
    labels_array = np.asarray(labels, dtype=bool)
    left = ((np.asarray(left_scores) >= left_threshold) == labels_array).astype(float)
    right = ((np.asarray(right_scores) >= right_threshold) == labels_array).astype(float)
    rng = np.random.default_rng(seed)
    deltas = np.empty(samples, dtype=float)
    for index in range(samples):
        chosen = rng.integers(0, len(labels), size=len(labels))
        deltas[index] = float(np.mean(left[chosen] - right[chosen]))
    low, high = np.quantile(deltas, [0.025, 0.975])
    return float(low), float(high)


def run_contextual_ambiguity_bakeoff(
    train: Sequence[ContextPair],
    dev: Sequence[ContextPair],
    test: Sequence[ContextPair],
    *,
    dim: int = 64,
    bootstrap_samples: int = 2000,
    seed: int = 20260712,
) -> dict[str, Any]:
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    feature_space = fit_feature_space(train, dim=dim)
    suite = ContextualRepresentationSuite(feature_space)
    dev_scores = _score_examples(suite, dev)
    test_scores = _score_examples(suite, test)
    dev_labels = [item.same_sense for item in dev]
    test_labels = [item.same_sense for item in test]
    thresholds = {name: _choose_threshold(dev_labels, dev_scores[name]) for name in suite.MODEL_NAMES}
    full_metrics = {
        name: _classification_metrics(test_labels, test_scores[name], thresholds[name])
        for name in suite.MODEL_NAMES
    }

    dev_seen = [index for index, item in enumerate(dev) if item.target_key in feature_space.train_target_keys]
    test_seen = [index for index, item in enumerate(test) if item.target_key in feature_space.train_target_keys]
    dev_seen_labels = [dev_labels[index] for index in dev_seen]
    test_seen_labels = [test_labels[index] for index in test_seen]
    seen_thresholds: dict[str, float] = {}
    seen_metrics: dict[str, dict[str, float | int]] = {}
    for name in suite.MODEL_NAMES:
        calibration = [dev_scores[name][index] for index in dev_seen]
        evaluation = [test_scores[name][index] for index in test_seen]
        threshold = _choose_threshold(dev_seen_labels, calibration) if dev_seen_labels else thresholds[name]
        seen_thresholds[name] = threshold
        seen_metrics[name] = _classification_metrics(test_seen_labels, evaluation, threshold)

    def dev_balanced(name: str) -> float:
        if not dev_seen_labels:
            return 0.0
        return float(
            _classification_metrics(
                dev_seen_labels,
                [dev_scores[name][index] for index in dev_seen],
                seen_thresholds[name],
            )["balanced_accuracy"]
        )

    density_model = max(sorted(suite.DENSITY_MODELS), key=lambda name: (dev_balanced(name), name))
    non_density_models = [name for name in suite.MODEL_NAMES if name not in suite.DENSITY_MODELS and name != "random"]
    non_density_model = max(non_density_models, key=lambda name: (dev_balanced(name), name))
    density_test_scores = [test_scores[density_model][index] for index in test_seen]
    baseline_test_scores = [test_scores[non_density_model][index] for index in test_seen]
    delta = float(seen_metrics[density_model]["accuracy"]) - float(seen_metrics[non_density_model]["accuracy"])
    ci_low, ci_high = _paired_accuracy_bootstrap(
        test_seen_labels,
        density_test_scores,
        seen_thresholds[density_model],
        baseline_test_scores,
        seen_thresholds[non_density_model],
        samples=bootstrap_samples,
        seed=seed,
    )
    coverage = len(test_seen) / len(test) if test else 0.0
    if len(test_seen) < 100 or coverage < 0.5:
        verdict = "insufficient_seen_target_data"
    elif delta > 0.02 and ci_low > 0.0:
        verdict = "density_context_state_leads"
    elif ci_high < 0.0:
        verdict = "non_density_context_backend_preferred"
    elif abs(delta) <= 0.01:
        verdict = "density_context_state_competitive"
    else:
        verdict = "inconclusive"

    return {
        "benchmark": BENCHMARK_VERSION,
        "splits": {"train": len(train), "dev": len(dev), "test": len(test)},
        "feature_space": {
            "dimension": dim,
            "idf_terms": len(feature_space.idf),
            "target_profiles": len(feature_space.target_profiles),
        },
        "seen_target_test_examples": len(test_seen),
        "seen_target_test_coverage": coverage,
        "thresholds_from_dev": thresholds,
        "models_full_test": full_metrics,
        "models_seen_target_test": seen_metrics,
        "selected_density_model": density_model,
        "selected_non_density_model": non_density_model,
        "density_accuracy_delta_seen_target": delta,
        "paired_accuracy_bootstrap_ci95": [ci_low, ci_high],
        "verdict": verdict,
        "decision_scope": {
            "canonical_store": "not tested; preserve typed temporal evidence and provenance",
            "semantic_backend": "contextual same-word sense discrimination",
            "density_claim": "target-specific PSD mixtures with explicit context conditioning",
        },
        "limitations": [
            "hash-based context features are not learned language representations",
            "target profiles are unsupervised and use only training contexts",
            "development labels tune thresholds and choose one model per family",
            "the benchmark does not test personal usefulness or long-term state updates",
            "official WiC is English noun/verb data and does not cover Russian personal semantics",
        ],
    }


def evaluate_wic(
    dataset_root: Path,
    *,
    output_path: Path,
    package_sha256: str | None = None,
    dim: int = 64,
    bootstrap_samples: int = 2000,
) -> dict[str, Any]:
    root = locate_wic_root(dataset_root)
    evaluation = run_contextual_ambiguity_bakeoff(
        load_wic_split(root, "train"),
        load_wic_split(root, "dev"),
        load_wic_split(root, "test"),
        dim=dim,
        bootstrap_samples=bootstrap_samples,
    )
    report = {
        "benchmark": BENCHMARK_VERSION,
        "dataset": {
            "name": "WiC 1.0",
            "license": WIC_LICENSE,
            "official_url": WIC_OFFICIAL_URL,
            "package_sha256": package_sha256,
            "raw_data_committed": False,
            "usage_purpose": "evaluation_only_no_model_training",
        },
        "evaluation": evaluation,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch-wic")
    fetch.add_argument("--output-dir", type=Path, required=True)
    fetch.add_argument("--url", default=WIC_OFFICIAL_URL)
    evaluate = commands.add_parser("evaluate-wic")
    evaluate.add_argument("--dataset-root", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--package-sha256")
    evaluate.add_argument("--dim", type=int, default=64)
    evaluate.add_argument("--bootstrap-samples", type=int, default=2000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "fetch-wic":
        result = fetch_wic_package(output_dir=args.output_dir, url=args.url)
    else:
        result = evaluate_wic(
            args.dataset_root,
            output_path=args.output,
            package_sha256=args.package_sha256,
            dim=args.dim,
            bootstrap_samples=args.bootstrap_samples,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
