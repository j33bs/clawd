from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

GOVERNANCE_MESSAGE = (
    "INV-003 c_lawd co-sign PENDING. Cannot run being_divergence() on real corpus.\n"
    "   Next step: jeebs messages c_lawd on Telegram with the INV-003 brief.\n"
    "   When c_lawd files a co-sign section in OPEN_QUESTIONS.md, update the\n"
    "   Co-Sign Block table in INV-003_being_divergence_design_brief.md and re-run."
)

MASKING_VARIANT_TAG = "[MASKING_VARIANT]"
MASKING_VARIANT_GOVERNANCE_MESSAGE = (
    "INV-003b masking co-sign PENDING. Cannot run --masking-variant on real corpus.\n"
    "   Next step: add `[MASKING_VARIANT: ✅ SIGNED]` to INV-003b_masking_variant_brief.md\n"
    "   after required co-sign, then re-run being_divergence.py --masking-variant."
)


class GovernanceError(Exception):
    pass


def _store_dir() -> Path:
    return Path(__file__).resolve().parent


def _workspace_dir() -> Path:
    return _store_dir().parent


def _repo_dir() -> Path:
    return _workspace_dir().parent


def _default_brief_path() -> Path:
    return _workspace_dir() / "docs" / "briefs" / "INV-003_being_divergence_design_brief.md"


def _default_masking_variant_brief_path() -> Path:
    return _workspace_dir() / "docs" / "briefs" / "INV-003b_masking_variant_brief.md"


def check_cosign(brief_path: str | None = None) -> None:
    path = Path(brief_path) if brief_path is not None else _default_brief_path()
    text = path.read_text(encoding="utf-8")
    if "c_lawd | ✅ SIGNED" not in text:
        raise GovernanceError(GOVERNANCE_MESSAGE)


def check_masking_variant_cosign(brief_path: str | None = None) -> None:
    path = Path(brief_path) if brief_path is not None else _default_masking_variant_brief_path()
    text = path.read_text(encoding="utf-8")
    if "[MASKING_VARIANT: ✅ SIGNED]" not in text:
        raise GovernanceError(MASKING_VARIANT_GOVERNANCE_MESSAGE)


@dataclass
class CoreMetrics:
    score: float
    random_baseline: float
    centroids: dict[str, np.ndarray]
    predicted_authors: list[str]
    n_beings: int
    per_being_scores: dict[str, dict[str, float | int]]


def _coerce_embedding(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        arr = value.astype(float).tolist()
        return arr if arr else None
    if isinstance(value, list):
        return [float(v) for v in value] if value else None
    return None


def _normalize_vector(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    an = _normalize_vector(a)
    bn = _normalize_vector(b)
    return float(1.0 - np.clip(np.dot(an, bn), -1.0, 1.0))


def _safe_silhouette(embeddings: np.ndarray, labels: list[Any]) -> float | None:
    if len(embeddings) < 3:
        return None
    unique = set(labels)
    if len(unique) < 2:
        return None
    if len(embeddings) <= len(unique):
        return None
    return float(silhouette_score(embeddings, labels))


def _compute_centroids(df: pd.DataFrame) -> dict[str, np.ndarray]:
    centroids: dict[str, np.ndarray] = {}
    for author, group in df.groupby("primary_author"):
        vectors = np.stack(group["embedding_vec"].to_list())
        centroids[author] = np.mean(vectors, axis=0)
    return centroids


def _predict_authors(df: pd.DataFrame, centroids: dict[str, np.ndarray]) -> list[str]:
    authors = sorted(centroids.keys())
    predictions: list[str] = []
    for vec in df["embedding_vec"].to_list():
        distances = [_cosine_distance(vec, centroids[a]) for a in authors]
        predictions.append(authors[int(np.argmin(distances))])
    return predictions


def _attribution_metrics(df: pd.DataFrame) -> CoreMetrics:
    centroids = _compute_centroids(df)
    predictions = _predict_authors(df, centroids)

    primary = df["primary_author"].tolist()
    correct_flags = [int(p == a) for p, a in zip(predictions, primary)]
    score = float(np.mean(correct_flags)) if correct_flags else 0.0

    n_beings = len(centroids)
    random_baseline = float(1.0 / n_beings) if n_beings else 0.0

    per_being: dict[str, dict[str, float | int]] = {}
    for author in sorted(centroids.keys()):
        idx = [i for i, a in enumerate(primary) if a == author]
        correct = int(sum(correct_flags[i] for i in idx))
        per_being[author] = {
            "n_sections": len(idx),
            "correctly_attributed": correct,
            "centroid_norm": float(np.linalg.norm(centroids[author])),
        }

    return CoreMetrics(
        score=score,
        random_baseline=random_baseline,
        centroids=centroids,
        predicted_authors=predictions,
        n_beings=n_beings,
        per_being_scores=per_being,
    )


def _canonical_series(df: pd.DataFrame) -> tuple[pd.Series, bool]:
    if "canonical_section_number" in df.columns and df["canonical_section_number"].notna().all():
        return df["canonical_section_number"].astype(int), False
    return pd.Series(np.arange(1, len(df) + 1), index=df.index), True


def _control_register(df: pd.DataFrame) -> dict[str, Any]:
    lengths = df["body"].astype(str).str.len()
    long_mask = lengths > 500

    long_df = df[long_mask]
    short_df = df[~long_mask]

    split_silhouette = {
        "long": _safe_silhouette(np.stack(long_df["embedding_vec"].to_list()), long_df["primary_author"].tolist())
        if len(long_df) >= 3
        else None,
        "short": _safe_silhouette(np.stack(short_df["embedding_vec"].to_list()), short_df["primary_author"].tolist())
        if len(short_df) >= 3
        else None,
    }

    overrepresented: list[str] = []
    for author, group in df.groupby("primary_author"):
        n_long = int((group["body"].astype(str).str.len() > 500).sum())
        n_total = len(group)
        if n_total > 0 and max(n_long, n_total - n_long) / n_total > 0.8:
            overrepresented.append(author)

    split_being_counts = {
        "long": int(long_df["primary_author"].nunique()),
        "short": int(short_df["primary_author"].nunique()),
    }

    flags: list[str] = []
    if overrepresented:
        flags.append("REGISTER_OVERREPRESENTATION")
    if split_being_counts["long"] < 2 or split_being_counts["short"] < 2:
        flags.append("REGISTER_SPLIT_TOO_NARROW")

    return {
        "split_sizes": {"long": int(len(long_df)), "short": int(len(short_df))},
        "author_silhouette_by_split": split_silhouette,
        "split_n_beings": split_being_counts,
        "overrepresented_beings": sorted(overrepresented),
        "flags": flags,
    }


def _control_topic(df: pd.DataFrame, n_beings: int) -> dict[str, Any]:
    n_samples = len(df)
    k = min(8, n_beings, max(1, n_samples - 1))
    if k < 2:
        return {
            "status": "RETRO_DARK",
            "reason": "Insufficient samples/beings for topic clustering",
            "k": int(k),
            "cluster_summaries": [],
            "dominant_clusters": [],
        }

    X = np.stack(df["embedding_vec"].to_list())
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    summaries: list[dict[str, Any]] = []
    dominant_clusters: list[int] = []

    for cluster_id in range(k):
        idx = np.where(labels == cluster_id)[0]
        sub = df.iloc[idx]
        dist = sub["primary_author"].value_counts(normalize=True)
        max_share = float(dist.max()) if len(dist) else 0.0
        max_author = dist.index[0] if len(dist) else None
        if max_share > 0.80:
            dominant_clusters.append(cluster_id)
        summaries.append(
            {
                "cluster_id": cluster_id,
                "n_sections": int(len(sub)),
                "max_being": max_author,
                "max_share": max_share,
                "being_distribution": {k: float(v) for k, v in dist.to_dict().items()},
            }
        )

    return {
        "status": "OK",
        "k": k,
        "cluster_summaries": summaries,
        "dominant_clusters": dominant_clusters,
        "flags": ["AUTHOR_DOMINANT_TOPIC"] if dominant_clusters else [],
    }


def _control_identity_drift(df: pd.DataFrame) -> dict[str, Any]:
    serial, fallback_used = _canonical_series(df)
    ordered = df.assign(_serial=serial).sort_values("_serial")

    mid = len(ordered) // 2
    early = ordered.iloc[:mid]
    late = ordered.iloc[mid:]

    out: dict[str, Any] = {
        "split_method": "canonical_section_number" if not fallback_used else "row_order_fallback",
        "fallback_used": fallback_used,
        "per_being": {},
    }

    for author in sorted(ordered["primary_author"].unique()):
        early_rows = early[early["primary_author"] == author]
        late_rows = late[late["primary_author"] == author]

        drift: float | None = None
        if len(early_rows) > 0 and len(late_rows) > 0:
            early_centroid = np.mean(np.stack(early_rows["embedding_vec"].to_list()), axis=0)
            late_centroid = np.mean(np.stack(late_rows["embedding_vec"].to_list()), axis=0)
            drift = _cosine_distance(early_centroid, late_centroid)

        out["per_being"][author] = {
            "early_n": int(len(early_rows)),
            "late_n": int(len(late_rows)),
            "drift_distance": drift,
        }

    return out


def _control_relational_state(df: pd.DataFrame) -> dict[str, Any]:
    if "trust_epoch" not in df.columns:
        return {"status": "RETRO_DARK", "reason": "trust_epoch column missing"}

    trust = df["trust_epoch"].fillna("").astype(str).str.strip()
    epochs = sorted([e for e in trust.unique() if e])
    if not epochs:
        return {"status": "RETRO_DARK", "reason": "trust_epoch has no non-empty values"}

    epoch_scores: dict[str, float] = {}
    for epoch in epochs:
        subset = df[trust == epoch]
        if len(subset) < 2 or subset["primary_author"].nunique() < 1:
            continue
        metrics = _attribution_metrics(subset)
        epoch_scores[epoch] = metrics.score

    if not epoch_scores:
        return {"status": "RETRO_DARK", "reason": "trust_epoch groups insufficient for scoring"}

    variance = float(np.var(list(epoch_scores.values()))) if len(epoch_scores) > 1 else 0.0
    return {
        "status": "OK",
        "centroid_scope": "within_epoch",
        "epoch_scores": epoch_scores,
        "variance": variance,
    }


def _compute_dual_embedding(df: pd.DataFrame, held_out_from: int) -> dict[str, Any]:
    full = _attribution_metrics(df)
    serial, fallback_used = _canonical_series(df)
    mask = serial >= held_out_from
    held_df = df[mask]

    held_score: float | None = None
    held_baseline: float | None = None
    if len(held_df) >= 1 and held_df["primary_author"].nunique() >= 1:
        held = _attribution_metrics(held_df)
        held_score = held.score
        held_baseline = held.random_baseline

    delta = (held_score - full.score) if held_score is not None else None

    return {
        "full_corpus_score": full.score,
        "held_out_score": held_score,
        "delta": delta,
        "held_out_from": held_out_from,
        "held_out_n": int(len(held_df)),
        "held_out_random_baseline": held_baseline,
        "split_method": "canonical_section_number" if not fallback_used else "row_order_fallback",
        "fallback_used": fallback_used,
    }


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_\-]+", text)


def _noun_like_tokens(bodies: list[str], top_k: int = 50) -> list[str]:
    c = Counter()
    for body in bodies:
        for tok in _tokenize(body):
            if (
                (tok[:1].isupper() and len(tok) > 1)
                or tok.startswith("RULE-")
                or tok.startswith("INV-")
                or "OPEN_QUESTIONS" in tok
                or re.search(r"[A-Z].*[0-9]|[0-9].*[A-Z]", tok)
            ):
                c[tok] += 1
    return [tok for tok, _ in c.most_common(top_k)]


def _remove_tokens(body: str, tokens: list[str]) -> str:
    if not tokens:
        return body
    out = body
    for token in tokens:
        out = re.sub(rf"\b{re.escape(token)}\b", "", out)
    return re.sub(r"\s+", " ", out).strip()


def _hash_embed_text(text: str, dim: int = 64) -> np.ndarray:
    vec = np.zeros(dim, dtype=float)
    for token in _tokenize(text.lower()):
        h = hashlib.blake2b(token.encode("utf-8"), digest_size=16).hexdigest()
        idx = int(h[:8], 16) % dim
        sign = 1.0 if int(h[8:10], 16) % 2 == 0 else -1.0
        vec[idx] += sign
    return _normalize_vector(vec)


def _reembed_bodies_real(bodies: list[str]) -> list[np.ndarray]:
    from sync import get_embedding_model  # local import by design

    model = get_embedding_model()
    vectors = model.encode(bodies, show_progress_bar=False)
    return [np.array(v, dtype=float) for v in vectors]


def _reembed_bodies_synthetic(bodies: list[str]) -> list[np.ndarray]:
    return [_hash_embed_text(body) for body in bodies]


def _load_real_corpus() -> pd.DataFrame:
    from sync import get_table  # local import by design

    table = get_table()
    return table.to_pandas()


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "authors" not in out.columns:
        raise ValueError("Corpus missing 'authors' column")
    if "embedding" not in out.columns:
        raise ValueError("Corpus missing 'embedding' column")
    if "body" not in out.columns:
        raise ValueError("Corpus missing 'body' column")

    out["authors"] = out["authors"].apply(lambda x: list(x) if isinstance(x, (list, np.ndarray)) else [])
    out = out[out["authors"].apply(lambda x: len(x) > 0)].copy()

    out["embedding_vec"] = out["embedding"].apply(_coerce_embedding)
    out = out[out["embedding_vec"].apply(lambda x: isinstance(x, list) and len(x) > 0)].copy()
    out["embedding_vec"] = out["embedding_vec"].apply(lambda x: np.array(x, dtype=float))

    out = out[out["body"].notna()].copy()
    out["body"] = out["body"].astype(str)

    out["primary_author"] = out["authors"].apply(lambda x: str(x[0]))
    out = out.reset_index(drop=True)
    return out


def _filter_masking_variant(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    for candidate in ("title", "header", "section_header"):
        if candidate in df.columns:
            series = df[candidate].fillna("").astype(str)
            mask = series.str.contains(re.escape(MASKING_VARIANT_TAG), regex=True)
            filtered = df[mask].copy().reset_index(drop=True)
            if filtered.empty:
                raise ValueError(
                    f"No sections matched {MASKING_VARIANT_TAG} in '{candidate}' for --masking-variant"
                )
            return filtered, candidate
    raise ValueError("Corpus missing header/title column required for --masking-variant filtering")


def _synthetic_rows(mode: str = "easy") -> list[dict[str, Any]]:
    being_vocab = {
        "being_a": ["compile", "deploy", "function", "pytest", "runtime", "refactor"],
        "being_b": ["ontology", "phenomenology", "consciousness", "meaning", "epistemic", "identity"],
        "being_c": ["governance", "protocol", "attestation", "append-only", "audit", "gate"],
        "being_d": ["analysis", "signal", "model", "context", "dialogue", "integration"],
    }

    if mode == "hard":
        shared = ["analysis", "context", "signal", "question", "response", "model"]
        for key in being_vocab:
            # Intentionally collapse vocab overlap to degrade attribution quality.
            being_vocab[key] = shared + ["shared", "baseline"]

    rows: list[dict[str, Any]] = []
    section = 1
    for author, vocab in being_vocab.items():
        for i in range(8):
            topic = " ".join(vocab)
            if mode == "hard":
                body = (
                    f"section {i} {topic}. "
                    f"OPEN_QUESTIONS INV-003 RULE-STORE-006 calibration evidence. "
                    f"{topic} shared vocabulary overlap across beings for controlled ambiguity."
                )
            else:
                body = (
                    f"{author} section {i} {topic}. "
                    f"OPEN_QUESTIONS INV-003 RULE-STORE-006 calibration evidence. "
                    f"{topic}"
                )
            emb = _hash_embed_text(body)
            rows.append(
                {
                    "authors": [author],
                    "title": (
                        f"{MASKING_VARIANT_TAG} Synthetic response {i}"
                        if i % 2 == 0
                        else f"Synthetic response {i}"
                    ),
                    "body": body,
                    "embedding": emb.tolist(),
                    "canonical_section_number": section,
                    "trust_epoch": "epoch_1" if i < 4 else "epoch_2",
                }
            )
            section += 1
    return rows


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _compute_verdict(
    score: float,
    baseline: float,
    author_silhouette: float | None,
    topic_silhouette: float | None,
    per_being_scores: dict[str, dict[str, float | int]],
    min_sections_per_author: int,
) -> str:
    if any(int(v["n_sections"]) < min_sections_per_author for v in per_being_scores.values()):
        return "INCONCLUSIVE"

    if (
        score >= baseline + 0.20
        and author_silhouette is not None
        and topic_silhouette is not None
        and author_silhouette > topic_silhouette
    ):
        return "DISPOSITIONAL"

    if score <= baseline + 0.05 or (
        author_silhouette is not None
        and topic_silhouette is not None
        and topic_silhouette >= author_silhouette
    ):
        return "SITUATIONAL"

    return "INCONCLUSIVE"


def _write_report(report: dict[str, Any], audit_dir: Path | None = None) -> Path:
    out_dir = audit_dir or (_workspace_dir() / "audit")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"being_divergence_{_timestamp_compact()}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path


def run_being_divergence(
    *,
    dry_run_synthetic: str | None = None,
    masking_variant: bool = False,
    noun_filter: bool = False,
    min_sections: int = 3,
    held_out_from: int = 82,
    brief_path: str | None = None,
    audit_dir: Path | None = None,
) -> dict[str, Any]:
    synthetic_mode = dry_run_synthetic

    if synthetic_mode is None:
        if masking_variant:
            check_masking_variant_cosign(brief_path=brief_path)
        else:
            check_cosign(brief_path=brief_path)
        source_df = _load_real_corpus()
        source_kind = "real"
    else:
        source_df = pd.DataFrame(_synthetic_rows(mode=synthetic_mode))
        source_kind = f"synthetic_{synthetic_mode}"

    df = _prepare_df(source_df)
    source_corpus_size = int(len(df))
    masking_filter_column: str | None = None
    if masking_variant:
        df, masking_filter_column = _filter_masking_variant(df)

    metrics = _attribution_metrics(df)
    X = np.stack(df["embedding_vec"].to_list())
    author_labels = df["primary_author"].tolist()

    author_sil = _safe_silhouette(X, author_labels)

    k_topic = min(8, metrics.n_beings, max(1, len(df) - 1))
    topic_sil: float | None = None
    if k_topic >= 2:
        km = KMeans(n_clusters=k_topic, random_state=42, n_init=10)
        topic_labels = km.fit_predict(X).tolist()
        topic_sil = _safe_silhouette(X, topic_labels)

    controls = {
        "C1_register": _control_register(df),
        "C2_topic": _control_topic(df, metrics.n_beings),
        "C3_identity_drift": _control_identity_drift(df),
        "C4_relational_state": _control_relational_state(df),
    }

    dual = _compute_dual_embedding(df, held_out_from=held_out_from)

    noun_delta: float | None = None
    noun_filter_applied = False
    if noun_filter:
        noun_filter_applied = True
        top_tokens = _noun_like_tokens(df["body"].tolist(), top_k=50)
        stripped_bodies = [_remove_tokens(body, top_tokens) for body in df["body"].tolist()]

        if source_kind.startswith("synthetic"):
            nf_vectors = _reembed_bodies_synthetic(stripped_bodies)
        else:
            nf_vectors = _reembed_bodies_real(stripped_bodies)

        nf_X = np.stack(nf_vectors)
        noun_author_sil = _safe_silhouette(nf_X, author_labels)
        if author_sil is not None and noun_author_sil is not None:
            noun_delta = float(noun_author_sil - author_sil)

    verdict = _compute_verdict(
        score=metrics.score,
        baseline=metrics.random_baseline,
        author_silhouette=author_sil,
        topic_silhouette=topic_sil,
        per_being_scores=metrics.per_being_scores,
        min_sections_per_author=min_sections,
    )

    report: dict[str, Any] = {
        "timestamp_utc": _timestamp_utc(),
        "corpus_size": int(len(df)),
        "source_corpus_size": source_corpus_size,
        "n_beings": int(metrics.n_beings),
        "random_baseline": metrics.random_baseline,
        "being_divergence_score": metrics.score,
        "author_silhouette": author_sil,
        "topic_silhouette": topic_sil,
        "verdict": verdict,
        "per_being_scores": metrics.per_being_scores,
        "controls": controls,
        "dual_embedding": dual,
        "noun_filter_applied": noun_filter_applied,
        "noun_filter_delta": noun_delta,
        "masking_variant": {
            "enabled": masking_variant,
            "tag": MASKING_VARIANT_TAG if masking_variant else None,
            "filter_column": masking_filter_column,
            "excluded_sections": int(source_corpus_size - len(df)) if masking_variant else 0,
        },
        "source": source_kind,
    }

    report_path = _write_report(report, audit_dir=audit_dir)
    report["audit_path"] = str(report_path)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="INV-003 being_divergence analysis")
    parser.add_argument(
        "--masking-variant",
        action="store_true",
        help=f"Filter to header/title entries containing {MASKING_VARIANT_TAG}",
    )
    parser.add_argument(
        "--dry-run-synthetic",
        nargs="?",
        const="easy",
        choices=["easy", "hard"],
        default=None,
        help="Bypass governance gate and run on deterministic synthetic corpus (default mode: easy)",
    )
    parser.add_argument("--noun-filter", action="store_true", help="Apply differential noun-filter check")
    parser.add_argument("--min-sections", type=int, default=3, help="Minimum sections per author for non-inconclusive verdict")
    parser.add_argument("--held-out-from", type=int, default=82, help="Held-out slice start section number")
    parser.add_argument(
        "--brief-path",
        type=str,
        default=None,
        help="Optional override for governing brief path (INV-003 or INV-003b with --masking-variant)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report = run_being_divergence(
        dry_run_synthetic=args.dry_run_synthetic,
        masking_variant=args.masking_variant,
        noun_filter=args.noun_filter,
        min_sections=args.min_sections,
        held_out_from=args.held_out_from,
        brief_path=args.brief_path,
    )

    print(f"being_divergence_score={report['being_divergence_score']:.6f}")
    print(f"random_baseline={report['random_baseline']:.6f}")
    print(f"verdict={report['verdict']}")
    print(f"audit_json={report['audit_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
