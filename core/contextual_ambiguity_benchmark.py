"""Contextual ambiguity bakeoff for candidate FVSC semantic backends.

The benchmark uses expert-labelled same-word/different-context pairs such as WiC.
All representation fitting uses the training split, decision thresholds use the
development split, and the test split is evaluated once.  Raw third-party data are
kept outside Git; reports contain only aggregate metrics and package hashes.

The density models in this module are deliberately simple, auditable baselines:
training contexts form target-specific PSD mixtures and each observed context
conditions that state.  A poor result tests this implementation, not every possible
density-matrix language model.
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
import tempfile
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
class ContextOccurrence:
    target_key: str
    tokens: tuple[str, ...]
    vector: np.ndarray


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
    """Download and safely extract the official WiC package for local evaluation."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "pilehvar.github.io":
        raise ValueError("WiC download must use the official pilehvar.github.io HTTPS host")

    output_dir.mkdir(parents=True, exist_ok=True)
    request = Request(
        url,
        headers={
            "User-Agent": "FVSC-contextual-ambiguity-benchmark/1.0 evaluation-only",
            "Accept": "application/zip",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # nosec: B310 - fixed host
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise ValueError("WiC package exceeds the configured download limit")
            chunks.append(chunk)
    data = b"".join(chunks)
    digest = hashlib.sha256(data).hexdigest()
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
        "package_sha256": digest,
        "package_bytes": len(data),
        "dataset_root": str(root),
        "usage_purpose": "evaluation_only_no_model_training",
    }
    (output_dir / "wic-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return metadata


def locate_wic_root(path: Path) -> Path:
    """Find the directory containing train/dev/test WiC files."""
    candidates = [path, *sorted(item for item in path.rglob("*") if item.is_dir())]
    for candidate in candidates:
        if all(_find_split_file(candidate, split, "data") is not None for split in ("train", "dev", "test")):
            if all(_find_split_file(candidate, split, "gold") is not None for split in ("train", "dev", "test")):
                return candidate
    raise FileNotFoundError("could not locate train/dev/test WiC data and gold files")


def _find_split_file(root: Path, split: str, kind: str) -> Path | None:
    exact = root / split / f"{split}.{kind}.txt"
    if exact.exists():
        return exact
    top = root / f"{split}.{kind}.txt"
    if top.exists():
        return top
    matches = sorted(root.rglob(f"{split}.{kind}.txt"))
    return matches[0] if matches else None


def load_wic_split(root: Path, split: str) -> tuple[ContextPair, ...]:
    split_clean = split.casefold()
    if split_clean not in {"train", "dev", "test"}:
        raise ValueError("split must be train, dev or test")
    data_path = _find_split_file(root, split_clean, "data")
    gold_path = _find_split_file(root, split_clean, "gold")
    if data_path is None or gold_path is None:
        raise FileNotFoundError(f"missing WiC {split_clean} files")
    data_lines = data_path.read_text(encoding="utf-8").splitlines()
    gold_lines = gold_path.read_text(encoding="utf-8").splitlines()
    if len(data_lines) != len(gold_lines):
        raise ValueError(f"WiC {split_clean} data/gold line counts differ")

    examples: list[ContextPair] = []
    for index, (data_line, gold_line) in enumerate(zip(data_lines, gold_lines), start=1):
        fields = data_line.split("\t")
        if len(fields) != 5:
            raise ValueError(f"invalid WiC {split_clean} data line {index}")
        target, pos, indexes, context1, context2 = fields
        try:
            raw_index1, raw_index2 = indexes.split("-", maxsplit=1)
            index1 = int(raw_index1)
            index2 = int(raw_index2)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid WiC target indexes at line {index}") from exc
        label = gold_line.strip().upper()
        if label not in {"T", "F"}:
            raise ValueError(f"invalid WiC gold label at line {index}")
        examples.append(
            ContextPair(
                split=split_clean,
                example_id=f"{split_clean}:{index}",
                target=target.strip(),
                pos=pos.strip().upper(),
                index1=index1,
                index2=index2,
                context1=context1.strip(),
                context2=context2.strip(),
                same_sense=label == "T",
            )
        )
    return tuple(examples)


def _context_tokens(sentence: str, target_index: int, target: str) -> tuple[str, ...]:
    raw_tokens = sentence.split()
    if 0 <= target_index < len(raw_tokens):
        raw_tokens = [token for index, token in enumerate(raw_tokens) if index != target_index]
    else:
        removed = False
        retained = []
        for token in raw_tokens:
            if not removed and target.casefold() in token.casefold():
                removed = True
                continue
            retained.append(token)
        raw_tokens = retained

    stopwords = set(DEFAULT_STOPWORDS_RU_EN)
    stopwords.add(target.casefold())
    normalized: list[str] = []
    for raw in raw_tokens:
        for token in _TOKEN_RE.findall(raw.casefold()):
            if len(token) >= 2 and token not in stopwords and not token.isdigit():
                normalized.append(token)
    return tuple(normalized)


def _all_occurrence_tokens(examples: Iterable[ContextPair]) -> list[tuple[str, tuple[str, ...]]]:
    rows: list[tuple[str, tuple[str, ...]]] = []
    for example in examples:
        rows.append((example.target_key, _context_tokens(example.context1, example.index1, example.target)))
        rows.append((example.target_key, _context_tokens(example.context2, example.index2, example.target)))
    return rows


def _fit_idf(examples: Sequence[ContextPair]) -> dict[str, float]:
    rows = _all_occurrence_tokens(examples)
    document_frequency: Counter[str] = Counter()
    for _target, tokens in rows:
        document_frequency.update(set(tokens))
    count = len(rows)
    return {
        token: math.log((1.0 + count) / (1.0 + frequency)) + 1.0
        for token, frequency in document_frequency.items()
    }


def _sparse_tfidf(tokens: Sequence[str], idf: Mapping[str, float]) -> dict[str, float]:
    counts = Counter(tokens)
    weighted = {
        token: float(frequency) * float(idf.get(token, 1.0))
        for token, frequency in counts.items()
    }
    norm = math.sqrt(sum(value * value for value in weighted.values()))
    if norm <= _EPS:
        return {}
    return {token: value / norm for token, value in weighted.items()}


def _sparse_cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return float(sum(value * right.get(token, 0.0) for token, value in left.items()))


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)


def _hashed_vector(tokens: Sequence[str], idf: Mapping[str, float], dim: int) -> np.ndarray:
    vector = np.zeros(dim, dtype=float)
    counts = Counter(tokens)
    for token, frequency in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "little") % dim
        sign = 1.0 if digest[8] & 1 else -1.0
        vector[index] += sign * float(frequency) * float(idf.get(token, 1.0))
    norm = float(np.linalg.norm(vector))
    if norm <= _EPS:
        return vector
    return vector / norm


def _normalize_density(operator: np.ndarray) -> np.ndarray:
    matrix = np.asarray(operator, dtype=float)
    matrix = (matrix + matrix.T) / 2.0
    trace = float(np.trace(matrix))
    if trace <= _EPS:
        dim = matrix.shape[0]
        return np.eye(dim, dtype=float) / dim
    return matrix / trace


def _fit_density(vectors: Sequence[np.ndarray], dim: int) -> np.ndarray:
    operator = np.zeros((dim, dim), dtype=float)
    for vector in vectors:
        operator += np.outer(vector, vector)
    return _normalize_density(operator)


def _fit_centroids(vectors: Sequence[np.ndarray], *, key: str, max_facets: int = 4) -> np.ndarray:
    if not vectors:
        raise ValueError("cannot fit centroids without vectors")
    matrix = np.vstack(vectors)
    count = len(vectors)
    k = min(max_facets, max(1, int(round(math.sqrt(count / 2.0)))))
    seed = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "little")
    first = seed % count
    chosen = [first]
    while len(chosen) < k:
        current = matrix[chosen]
        similarities = matrix @ current.T
        nearest = np.max(similarities, axis=1)
        for index in chosen:
            nearest[index] = 1.0
        chosen.append(int(np.argmin(nearest)))
    centroids = np.array(matrix[chosen], copy=True)

    for _iteration in range(20):
        assignments = np.argmax(matrix @ centroids.T, axis=1)
        updated = []
        for cluster in range(k):
            members = matrix[assignments == cluster]
            if len(members) == 0:
                updated.append(centroids[cluster])
                continue
            centroid = np.mean(members, axis=0)
            norm = float(np.linalg.norm(centroid))
            updated.append(centroid / norm if norm > _EPS else centroids[cluster])
        new_centroids = np.vstack(updated)
        if np.allclose(new_centroids, centroids, atol=1e-10):
            centroids = new_centroids
            break
        centroids = new_centroids
    return centroids


def _profile(vectors: Sequence[np.ndarray], *, key: str, dim: int) -> TargetProfile:
    density = _fit_density(vectors, dim)
    eigenvalues, eigenvectors = np.linalg.eigh(density)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    eigenvectors = eigenvectors[:, order]
    active = eigenvalues > 1e-10
    eigenvalues = eigenvalues[active][: min(8, dim)]
    eigenvectors = eigenvectors[:, active][:, : min(8, dim)]
    if eigenvalues.size == 0:
        eigenvalues = np.asarray([1.0])
        eigenvectors = np.eye(dim, 1)
    eigenvalues = eigenvalues / max(float(np.sum(eigenvalues)), _EPS)
    centroids = _fit_centroids(vectors, key=key)
    return TargetProfile(
        density=density,
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        centroids=centroids,
        occurrence_count=len(vectors),
    )


def fit_feature_space(train: Sequence[ContextPair], *, dim: int = 64) -> ContextFeatureSpace:
    if dim < 8:
        raise ValueError("dim must be at least 8")
    idf = _fit_idf(train)
    grouped: dict[str, list[np.ndarray]] = defaultdict(list)
    all_vectors: list[np.ndarray] = []
    for target_key, tokens in _all_occurrence_tokens(train):
        vector = _hashed_vector(tokens, idf, dim)
        if float(np.linalg.norm(vector)) <= _EPS:
            continue
        grouped[target_key].append(vector)
        all_vectors.append(vector)
    if not all_vectors:
        all_vectors = [np.eye(dim, dtype=float)[0]]
    target_profiles = {
        key: _profile(vectors, key=key, dim=dim)
        for key, vectors in sorted(grouped.items())
        if vectors
    }
    global_profile = _profile(all_vectors, key="__global__", dim=dim)
    return ContextFeatureSpace(
        idf=idf,
        dim=dim,
        target_profiles=target_profiles,
        global_profile=global_profile,
        train_target_keys=frozenset(target_profiles),
    )


def _condition_density(density: np.ndarray, context: np.ndarray, *, floor: float = 0.15) -> np.ndarray:
    if float(np.linalg.norm(context)) <= _EPS:
        return density
    projector = np.outer(context, context)
    root_floor = math.sqrt(floor)
    effect_root = root_floor * np.eye(len(context)) + (math.sqrt(1.0 + floor) - root_floor) * projector
    posterior = effect_root @ density @ effect_root
    return _normalize_density(posterior)


def _density_overlap(left: np.ndarray, right: np.ndarray) -> float:
    numerator = float(np.trace(left @ right))
    denominator = math.sqrt(
        max(float(np.trace(left @ left)), _EPS)
        * max(float(np.trace(right @ right)), _EPS)
    )
    return float(np.clip(numerator / denominator, 0.0, 1.0))


def _facet_distribution(profile: TargetProfile, context: np.ndarray) -> np.ndarray:
    projections = profile.eigenvectors.T @ context
    weights = profile.eigenvalues * np.square(projections)
    total = float(np.sum(weights))
    if total <= _EPS:
        return np.full(len(profile.eigenvalues), 1.0 / len(profile.eigenvalues))
    return weights / total


def _centroid_distribution(profile: TargetProfile, context: np.ndarray) -> np.ndarray:
    similarities = np.clip(profile.centroids @ context, -1.0, 1.0)
    logits = 5.0 * similarities
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

    def score(self, example: ContextPair) -> dict[str, float]:
        tokens1 = _context_tokens(example.context1, example.index1, example.target)
        tokens2 = _context_tokens(example.context2, example.index2, example.target)
        sparse1 = _sparse_tfidf(tokens1, self.feature_space.idf)
        sparse2 = _sparse_tfidf(tokens2, self.feature_space.idf)
        vector1 = _hashed_vector(tokens1, self.feature_space.idf, self.feature_space.dim)
        vector2 = _hashed_vector(tokens2, self.feature_space.idf, self.feature_space.dim)
        profile = self.feature_space.target_profiles.get(
            example.target_key,
            self.feature_space.global_profile,
        )
        posterior1 = _condition_density(profile.density, vector1)
        posterior2 = _condition_density(profile.density, vector2)
        facet1 = _facet_distribution(profile, vector1)
        facet2 = _facet_distribution(profile, vector2)
        centroid1 = _centroid_distribution(profile, vector1)
        centroid2 = _centroid_distribution(profile, vector2)
        random_digest = hashlib.sha256(example.example_id.encode("utf-8")).digest()
        random_score = int.from_bytes(random_digest[:8], "little") / float(2**64 - 1)
        return {
            "token_jaccard": _jaccard(tokens1, tokens2),
            "tfidf_cosine": _sparse_cosine(sparse1, sparse2),
            "hashed_context_cosine": float(np.clip(np.dot(vector1, vector2), -1.0, 1.0)),
            "explicit_kmeans_facets": _bhattacharyya(centroid1, centroid2),
            "density_posterior_overlap": _density_overlap(posterior1, posterior2),
            "density_eigenfacet_overlap": _bhattacharyya(facet1, facet2),
            "random": random_score,
        }


def _roc_auc(labels: Sequence[bool], scores: Sequence[float]) -> float:
    positives = [score for label, score in zip(labels, scores) if label]
    negatives = [score for label, score in zip(labels, scores) if not label]
    if not positives or not negatives:
        return 0.5
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative + _EPS:
                wins += 1.0
            elif abs(positive - negative) <= _EPS:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _threshold_candidates(scores: Sequence[float]) -> list[float]:
    unique = sorted(set(float(score) for score in scores))
    if not unique:
        return [0.5]
    candidates = [unique[0] - 1e-9]
    candidates.extend((left + right) / 2.0 for left, right in zip(unique, unique[1:]))
    candidates.append(unique[-1] + 1e-9)
    return candidates


def _classification_metrics(
    labels: Sequence[bool],
    scores: Sequence[float],
    threshold: float,
) -> dict[str, float | int]:
    predictions = [score >= threshold for score in scores]
    tp = sum(label and prediction for label, prediction in zip(labels, predictions))
    tn = sum((not label) and (not prediction) for label, prediction in zip(labels, predictions))
    fp = sum((not label) and prediction for label, prediction in zip(labels, predictions))
    fn = sum(label and (not prediction) for label, prediction in zip(labels, predictions))
    total = len(labels)
    accuracy = (tp + tn) / total if total else 0.0
    tpr = tp / (tp + fn) if tp + fn else 0.0
    tnr = tn / (tn + fp) if tn + fp else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tpr
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "examples": total,
        "accuracy": accuracy,
        "balanced_accuracy": (tpr + tnr) / 2.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": _roc_auc(labels, scores),
        "threshold": threshold,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def _choose_threshold(labels: Sequence[bool], scores: Sequence[float]) -> float:
    best_threshold = 0.5
    best_key = (-1.0, -1.0, float("-inf"))
    for threshold in _threshold_candidates(scores):
        metrics = _classification_metrics(labels, scores, threshold)
        key = (
            float(metrics["balanced_accuracy"]),
            float(metrics["accuracy"]),
            -abs(threshold - 0.5),
        )
        if key > best_key:
            best_key = key
            best_threshold = threshold
    return best_threshold


def _score_examples(
    suite: ContextualRepresentationSuite,
    examples: Sequence[ContextPair],
) -> dict[str, list[float]]:
    scores = {name: [] for name in suite.MODEL_NAMES}
    for example in examples:
        values = suite.score(example)
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
    left_correct = (np.asarray(left_scores) >= left_threshold) == labels_array
    right_correct = (np.asarray(right_scores) >= right_threshold) == labels_array
    rng = np.random.default_rng(seed)
    deltas = np.empty(samples, dtype=float)
    for index in range(samples):
        chosen = rng.integers(0, len(labels), size=len(labels))
        deltas[index] = float(np.mean(left_correct[chosen] - right_correct[chosen]))
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
    dev_labels = [example.same_sense for example in dev]
    test_labels = [example.same_sense for example in test]

    thresholds = {
        name: _choose_threshold(dev_labels, dev_scores[name])
        for name in suite.MODEL_NAMES
    }
    full_metrics = {
        name: _classification_metrics(test_labels, test_scores[name], thresholds[name])
        for name in suite.MODEL_NAMES
    }

    seen_dev_indices = [
        index for index, example in enumerate(dev)
        if example.target_key in feature_space.train_target_keys
    ]
    seen_test_indices = [
        index for index, example in enumerate(test)
        if example.target_key in feature_space.train_target_keys
    ]
    seen_dev_labels = [dev_labels[index] for index in seen_dev_indices]
    seen_test_labels = [test_labels[index] for index in seen_test_indices]
    seen_thresholds: dict[str, float] = {}
    seen_metrics: dict[str, dict[str, float | int]] = {}
    for name in suite.MODEL_NAMES:
        calibration_scores = [dev_scores[name][index] for index in seen_dev_indices]
        evaluation_scores = [test_scores[name][index] for index in seen_test_indices]
        threshold = (
            _choose_threshold(seen_dev_labels, calibration_scores)
            if seen_dev_labels else thresholds[name]
        )
        seen_thresholds[name] = threshold
        seen_metrics[name] = _classification_metrics(
            seen_test_labels,
            evaluation_scores,
            threshold,
        )

    density_candidates = sorted(suite.DENSITY_MODELS)
    non_density_candidates = [
        name for name in suite.MODEL_NAMES
        if name not in suite.DENSITY_MODELS and name != "random"
    ]
    selected_density = max(
        density_candidates,
        key=lambda name: (
            _classification_metrics(
                seen_dev_labels,
                [dev_scores[name][index] for index in seen_dev_indices],
                seen_thresholds[name],
            )["balanced_accuracy"] if seen_dev_labels else 0.0,
            name,
        ),
    )
    selected_non_density = max(
        non_density_candidates,
        key=lambda name: (
            _classification_metrics(
                seen_dev_labels,
                [dev_scores[name][index] for index in seen_dev_indices],
                seen_thresholds[name],
            )["balanced_accuracy"] if seen_dev_labels else 0.0,
            name,
        ),
    )
    density_seen_scores = [test_scores[selected_density][index] for index in seen_test_indices]
    baseline_seen_scores = [test_scores[selected_non_density][index] for index in seen_test_indices]
    density_accuracy = float(seen_metrics[selected_density]["accuracy"])
    baseline_accuracy = float(seen_metrics[selected_non_density]["accuracy"])
    delta = density_accuracy - baseline_accuracy
    ci_low, ci_high = _paired_accuracy_bootstrap(
        seen_test_labels,
        density_seen_scores,
        seen_thresholds[selected_density],
        baseline_seen_scores,
        seen_thresholds[selected_non_density],
        samples=bootstrap_samples,
        seed=seed,
    )
    coverage = len(seen_test_indices) / len(test) if test else 0.0

    if len(seen_test_indices) < 100 or coverage < 0.5:
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
        "splits": {
            "train": len(train),
            "dev": len(dev),
            "test": len(test),
        },
        "feature_space": {
            "dimension": dim,
            "idf_terms": len(feature_space.idf),
            "target_profiles": len(feature_space.target_profiles),
        },
        "seen_target_test_examples": len(seen_test_indices),
        "seen_target_test_coverage": coverage,
        "thresholds_from_dev": thresholds,
        "models_full_test": full_metrics,
        "models_seen_target_test": seen_metrics,
        "selected_density_model": selected_density,
        "selected_non_density_model": selected_non_density,
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
    train = load_wic_split(root, "train")
    dev = load_wic_split(root, "dev")
    test = load_wic_split(root, "test")
    evaluation = run_contextual_ambiguity_bakeoff(
        train,
        dev,
        test,
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
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch-wic")
    fetch.add_argument("--output-dir", type=Path, required=True)
    fetch.add_argument("--url", default=WIC_OFFICIAL_URL)

    evaluate = subparsers.add_parser("evaluate-wic")
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
