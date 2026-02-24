from __future__ import annotations

import json
from pathlib import Path
import sys

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
