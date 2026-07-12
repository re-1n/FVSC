from __future__ import annotations

from pathlib import Path

from core.contextual_ambiguity_benchmark import (
    BENCHMARK_VERSION,
    ContextualRepresentationSuite,
    evaluate_wic,
    fit_feature_space,
    load_wic_split,
    run_contextual_ambiguity_bakeoff,
)


def _write_split(root: Path, split: str, rows: list[tuple[str, str, str, str, str, str]]) -> None:
    directory = root / split
    directory.mkdir(parents=True, exist_ok=True)
    data = []
    gold = []
    for target, pos, indexes, context1, context2, label in rows:
        data.append("\t".join((target, pos, indexes, context1, context2)))
        gold.append(label)
    (directory / f"{split}.data.txt").write_text("\n".join(data) + "\n", encoding="utf-8")
    (directory / f"{split}.gold.txt").write_text("\n".join(gold) + "\n", encoding="utf-8")


def _fixture_dataset(root: Path) -> None:
    financial_same = (
        "bank", "N", "1-2",
        "The bank approved our loan",
        "A local bank offered credit",
        "T",
    )
    financial_different = (
        "bank", "N", "1-3",
        "The bank approved our loan",
        "We rested near the river bank",
        "F",
    )
    river_same = (
        "bank", "N", "3-3",
        "We walked along the river bank",
        "They sat beside the muddy bank",
        "T",
    )
    light_same = (
        "light", "N", "1-2",
        "The light filled the room",
        "A bright light appeared suddenly",
        "T",
    )
    light_different = (
        "light", "N", "1-2",
        "The light filled the room",
        "This suitcase feels light today",
        "F",
    )
    weight_same = (
        "light", "N", "3-2",
        "The package is very light",
        "A light parcel arrived today",
        "T",
    )

    train_rows = [
        financial_same,
        financial_different,
        river_same,
        light_same,
        light_different,
        weight_same,
    ] * 3
    dev_rows = [financial_same, financial_different, river_same, light_same, light_different, weight_same]
    test_rows = [river_same, financial_different, financial_same, weight_same, light_different, light_same]
    _write_split(root, "train", train_rows)
    _write_split(root, "dev", dev_rows)
    _write_split(root, "test", test_rows)


def test_load_wic_split_and_feature_space(tmp_path: Path) -> None:
    _fixture_dataset(tmp_path)
    train = load_wic_split(tmp_path, "train")
    assert len(train) == 18
    assert train[0].target_key == "bank::N"
    assert train[0].same_sense is True

    feature_space = fit_feature_space(train, dim=32)
    assert feature_space.dim == 32
    assert {"bank::N", "light::N"} <= feature_space.train_target_keys
    suite = ContextualRepresentationSuite(feature_space)
    scores = suite.score(train[0])
    assert tuple(scores) == suite.MODEL_NAMES
    assert all(-1.0 <= value <= 1.0 for value in scores.values())


def test_contextual_bakeoff_is_deterministic(tmp_path: Path) -> None:
    _fixture_dataset(tmp_path)
    train = load_wic_split(tmp_path, "train")
    dev = load_wic_split(tmp_path, "dev")
    test = load_wic_split(tmp_path, "test")

    first = run_contextual_ambiguity_bakeoff(
        train,
        dev,
        test,
        dim=32,
        bootstrap_samples=100,
    )
    second = run_contextual_ambiguity_bakeoff(
        train,
        dev,
        test,
        dim=32,
        bootstrap_samples=100,
    )

    assert first == second
    assert first["benchmark"] == BENCHMARK_VERSION
    assert first["splits"] == {"train": 18, "dev": 6, "test": 6}
    assert first["seen_target_test_coverage"] == 1.0
    assert set(first["models_full_test"]) == set(ContextualRepresentationSuite.MODEL_NAMES)
    assert first["selected_density_model"] in ContextualRepresentationSuite.DENSITY_MODELS
    assert first["verdict"] in {
        "insufficient_seen_target_data",
        "density_context_state_leads",
        "non_density_context_backend_preferred",
        "density_context_state_competitive",
        "inconclusive",
    }


def test_evaluate_wic_writes_aggregate_report(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _fixture_dataset(dataset)
    output = tmp_path / "report.json"

    report = evaluate_wic(
        dataset,
        output_path=output,
        package_sha256="a" * 64,
        dim=32,
        bootstrap_samples=100,
    )

    assert output.exists()
    assert report["benchmark"] == BENCHMARK_VERSION
    assert report["dataset"]["package_sha256"] == "a" * 64
    assert report["dataset"]["raw_data_committed"] is False
    assert report["evaluation"]["splits"]["test"] == 6
