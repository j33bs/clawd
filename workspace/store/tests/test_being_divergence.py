from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd
import pytest

STORE_ROOT = Path(__file__).resolve().parents[1]
if str(STORE_ROOT) not in sys.path:
    sys.path.insert(0, str(STORE_ROOT))

import being_divergence
from being_divergence import GovernanceError, check_cosign, run_being_divergence


def test_cosign_gate_blocks_real_corpus(tmp_path: Path) -> None:
    brief = tmp_path / "brief.md"
    brief.write_text(
        "| Co-owner | Status |\n| c_lawd | ⬜ PENDING |\n",
        encoding="utf-8",
    )

    with pytest.raises(GovernanceError) as exc:
        check_cosign(str(brief))

    assert str(exc.value) == being_divergence.GOVERNANCE_MESSAGE

    with pytest.raises(GovernanceError):
        run_being_divergence(
            dry_run_synthetic=None,
            brief_path=str(brief),
            audit_dir=tmp_path,
        )


def test_synthetic_easy_corpus_scores_high(tmp_path: Path) -> None:
    report = run_being_divergence(
        dry_run_synthetic="easy",
        audit_dir=tmp_path,
    )
    assert report["being_divergence_score"] > 0.8


def test_synthetic_hard_corpus_degrades(tmp_path: Path) -> None:
    easy = run_being_divergence(dry_run_synthetic="easy", audit_dir=tmp_path)
    hard = run_being_divergence(dry_run_synthetic="hard", audit_dir=tmp_path)

    assert hard["being_divergence_score"] <= hard["random_baseline"] + 0.15 or (
        hard["being_divergence_score"] < easy["being_divergence_score"]
    )


def test_all_four_controls_present_in_output(tmp_path: Path) -> None:
    report = run_being_divergence(
        dry_run_synthetic="easy",
        audit_dir=tmp_path,
    )
    controls = report["controls"]
    assert set(controls.keys()) == {
        "C1_register",
        "C2_topic",
        "C3_identity_drift",
        "C4_relational_state",
    }


def test_output_file_written(tmp_path: Path) -> None:
    report = run_being_divergence(
        dry_run_synthetic="easy",
        audit_dir=tmp_path,
    )

    out = Path(report["audit_path"])
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["verdict"] == report["verdict"]


def test_random_baseline_calculated_correctly(tmp_path: Path) -> None:
    report = run_being_divergence(
        dry_run_synthetic="easy",
        audit_dir=tmp_path,
    )
    assert report["n_beings"] == 4
    assert report["random_baseline"] == pytest.approx(1.0 / 4.0)


def test_noun_filter_runs_without_error(tmp_path: Path) -> None:
    report = run_being_divergence(
        dry_run_synthetic="easy",
        noun_filter=True,
        audit_dir=tmp_path,
    )
    assert report["noun_filter_applied"] is True
    assert "noun_filter_delta" in report
    assert Path(report["audit_path"]).exists()


def test_masking_variant_filters_synthetic_subcorpus(tmp_path: Path) -> None:
    full = run_being_divergence(
        dry_run_synthetic="easy",
        audit_dir=tmp_path,
    )
    masked = run_being_divergence(
        dry_run_synthetic="easy",
        masking_variant=True,
        audit_dir=tmp_path,
    )

    assert masked["corpus_size"] < full["corpus_size"]
    assert masked["source_corpus_size"] == full["corpus_size"]
    assert masked["masking_variant"]["enabled"] is True
    assert masked["masking_variant"]["excluded_sections"] > 0


def test_masking_variant_reports_filtered_silhouettes_and_controls(tmp_path: Path) -> None:
    report = run_being_divergence(
        dry_run_synthetic="easy",
        masking_variant=True,
        audit_dir=tmp_path,
    )

    assert "author_silhouette" in report
    assert "topic_silhouette" in report
    assert set(report["controls"].keys()) == {
        "C1_register",
        "C2_topic",
        "C3_identity_drift",
        "C4_relational_state",
    }


def test_masking_variant_gate_blocks_real_corpus_when_unsigned(tmp_path: Path) -> None:
    brief = tmp_path / "masking_brief.md"
    brief.write_text("# INV-003b\n[MASKING_VARIANT: ⬜ PENDING]\n", encoding="utf-8")

    with pytest.raises(GovernanceError) as exc:
        run_being_divergence(
            dry_run_synthetic=None,
            masking_variant=True,
            brief_path=str(brief),
            audit_dir=tmp_path,
        )

    assert str(exc.value) == being_divergence.MASKING_VARIANT_GOVERNANCE_MESSAGE


def test_masking_variant_gate_allows_signed_real_and_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    brief = tmp_path / "masking_brief.md"
    brief.write_text("# INV-003b\n[MASKING_VARIANT: ✅ SIGNED]\n", encoding="utf-8")

    rows = [
        {"authors": ["being_a"], "title": "[MASKING_VARIANT] a0", "body": "alpha", "embedding": [1.0, 0.0], "canonical_section_number": 1, "trust_epoch": "building"},
        {"authors": ["being_a"], "title": "[MASKING_VARIANT] a1", "body": "alpha alpha", "embedding": [0.9, 0.1], "canonical_section_number": 2, "trust_epoch": "building"},
        {"authors": ["being_b"], "title": "[MASKING_VARIANT] b0", "body": "beta", "embedding": [0.0, 1.0], "canonical_section_number": 3, "trust_epoch": "building"},
        {"authors": ["being_b"], "title": "[MASKING_VARIANT] b1", "body": "beta beta", "embedding": [0.1, 0.9], "canonical_section_number": 4, "trust_epoch": "building"},
        {"authors": ["being_b"], "title": "unmasked", "body": "beta off-topic", "embedding": [0.2, 0.8], "canonical_section_number": 5, "trust_epoch": "building"},
    ]
    monkeypatch.setattr(being_divergence, "_load_real_corpus", lambda: pd.DataFrame(rows))

    report = run_being_divergence(
        dry_run_synthetic=None,
        masking_variant=True,
        brief_path=str(brief),
        audit_dir=tmp_path,
    )

    assert report["source"] == "real"
    assert report["source_corpus_size"] == 5
    assert report["corpus_size"] == 4
    assert report["masking_variant"]["filter_column"] == "title"


def test_masking_variant_dry_run_synthetic_bypasses_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _explode(_: str | None = None) -> None:
        raise AssertionError("gate should not run for dry-run synthetic")

    monkeypatch.setattr(being_divergence, "check_masking_variant_cosign", _explode)
    report = run_being_divergence(
        dry_run_synthetic="easy",
        masking_variant=True,
        audit_dir=tmp_path,
    )
    assert report["source"].startswith("synthetic")


def test_masking_variant_raises_when_no_matching_tag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _rows_no_tag(mode: str = "easy") -> list[dict[str, object]]:
        return [
            {
                "authors": ["being_a"],
                "title": "Synthetic response",
                "body": "alpha text",
                "embedding": [1.0, 0.0],
                "canonical_section_number": 1,
                "trust_epoch": "building",
            },
            {
                "authors": ["being_b"],
                "title": "Another response",
                "body": "beta text",
                "embedding": [0.0, 1.0],
                "canonical_section_number": 2,
                "trust_epoch": "building",
            },
        ]

    monkeypatch.setattr(being_divergence, "_synthetic_rows", _rows_no_tag)
    with pytest.raises(ValueError, match="No sections matched"):
        run_being_divergence(
            dry_run_synthetic="easy",
            masking_variant=True,
            audit_dir=tmp_path,
        )


def test_parser_accepts_masking_variant_flag() -> None:
    args = being_divergence.build_parser().parse_args(["--masking-variant", "--dry-run-synthetic"])
    assert args.masking_variant is True
    assert args.dry_run_synthetic == "easy"
