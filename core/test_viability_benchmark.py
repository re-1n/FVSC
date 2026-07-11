from __future__ import annotations

from core.viability_benchmark import run_benchmark


def test_viability_benchmark_report_is_deterministic_and_bounded() -> None:
    report_a = run_benchmark(dims=(16,), bootstrap_samples=100, seed=7)
    report_b = run_benchmark(dims=(16,), bootstrap_samples=100, seed=7)

    assert report_a == report_b
    assert report_a["benchmark"] == "fvsc-controlled-directionality-v4"
    assert report_a["n_directional_pairs"] > 0

    for model_name in (
        "fvsc_density_mass_preserving",
        "fvsc_density_trace_normalized_control",
        "trace_mass_only",
        "direct_parser_edges",
    ):
        model = report_a["models"][model_name]
        assert 0.0 <= model["accuracy"] <= 1.0
        assert 0.0 <= model["coverage"] <= 1.0
        assert 0.0 <= model["p_vs_chance_one_sided"] <= 1.0
        assert 0.0 <= model["ranking_auc"] <= 1.0
        assert model["ranking_comparisons"] > 0
        assert len(model["ci95"]) == 2
        assert 0.0 <= model["ci95"][0] <= model["ci95"][1] <= 1.0

    normalized = report_a["models"]["fvsc_density_trace_normalized_control"]
    assert normalized["accuracy"] == 0.5
    assert normalized["ranking_auc"] == 0.5

    assert report_a["decision"]["controlled_viability"] in {
        "pass",
        "inconclusive",
        "fail",
    }
    valid_comparisons = {
        "demonstrated_on_controlled_set",
        "not_distinguishable_from_baseline",
        "worse_than_baseline",
    }
    assert report_a["decision"]["matrix_added_value_over_direct_edges"] in valid_comparisons
    assert report_a["decision"]["direction_beyond_trace_mass"] in valid_comparisons
