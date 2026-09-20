"""
Phase 4: the compatibility-rules + confidence engine -- the actual safety gate.

Verdicts are decided by DETERMINISTIC attribute comparison, never by the
embedding/confidence score. That score is an auxiliary signal for the human
reviewer, not a vote in the verdict -- this is the whole point of the hybrid
architecture: AI ranks candidates, explicit rules decide conflicts.

One deliberate departure from Samanvay's own HARD_ATTRIBUTES: the dataset's
generator never varies connection type (flanged/screwed) when building its
hard negatives, so "ends" isn't in categories.py's hard list. But the PS
explicitly calls out "different connection types" as a case that must not be
silently merged, and our own custom_gap_test_set was built specifically to
test it. So CRITICAL_ATTRIBUTES extends HARD_ATTRIBUTES with "ends" wherever
a category actually has that field -- Samanvay's own omission looks like a
generator-simplicity choice, not a considered claim that connection type is
safe to ignore.
"""
from app.attributes import HARD_ATTRIBUTES

_HAS_ENDS = {"gate_valve", "globe_valve", "ball_valve", "check_valve", "spiral_gasket", "wnrf_flange"}

CRITICAL_ATTRIBUTES: dict[str, list[str]] = {
    cat: attrs + (["ends"] if cat in _HAS_ENDS else [])
    for cat, attrs in HARD_ATTRIBUTES.items()
}

# Real, verifiable engineering equivalences (not invented): ASTM A106 Grade B
# is itself a carbon steel pipe specification, so a record naming the
# standard and one naming the base material describe the same material grade.
# Kept intentionally small -- each entry needs a defensible engineering
# justification, not just two strings that look alike.
MATERIAL_EQUIVALENCE: dict[str, set[str]] = {
    "material": {
        frozenset({"A106 GR B", "CARBON STEEL"}): "ASTM A106 Grade B is a carbon steel pipe specification",
    }
}


def _values_equal(a, b) -> bool:
    if a is None or b is None:
        return False
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def _equivalence_reason(attr: str, a, b) -> str | None:
    if attr != "material" or a is None or b is None:
        return None
    pair = frozenset({a, b})
    for equiv_pair, reason in MATERIAL_EQUIVALENCE["material"].items():
        if pair == equiv_pair:
            return reason
    return None


def evaluate_pair(
    category_a: str | None,
    attrs_a: dict,
    category_b: str | None,
    attrs_b: dict,
    embedding_similarity: float | None = None,
) -> dict:
    reasons: list[str] = []
    matching, conflicting, missing, equivalent = [], [], [], []

    if category_a is None or category_b is None:
        return {
            "verdict": "INSUFFICIENT_INFORMATION",
            "confidence": 0.0,
            "matching_attributes": [], "conflicting_attributes": [],
            "missing_attributes": [], "equivalent_attributes": [],
            "reasons": ["Category could not be determined for at least one record; cannot compare attributes."],
            "embedding_similarity": embedding_similarity,
        }

    if category_a != category_b:
        return {
            "verdict": "CONFLICT",
            "confidence": 0.0,
            "matching_attributes": [], "conflicting_attributes": [],
            "missing_attributes": [], "equivalent_attributes": [],
            "reasons": [f"Different material categories: {category_a} vs {category_b}."],
            "embedding_similarity": embedding_similarity,
        }

    critical = CRITICAL_ATTRIBUTES.get(category_a, [])
    for attr in critical:
        va, vb = attrs_a.get(attr), attrs_b.get(attr)
        if va is None or vb is None:
            missing.append(attr)
            reasons.append(f"{attr}: missing on {'A' if va is None else 'B'} side -- cannot confirm match.")
            continue
        if _values_equal(va, vb):
            matching.append(attr)
            reasons.append(f"{attr}: match ({va}).")
            continue
        equiv_reason = _equivalence_reason(attr, va, vb)
        if equiv_reason:
            equivalent.append(attr)
            reasons.append(f"{attr}: functionally equivalent ({va} vs {vb}) -- {equiv_reason}.")
            continue
        conflicting.append({"attribute": attr, "value_a": va, "value_b": vb})
        reasons.append(f"{attr}: CONFLICT ({va} vs {vb}).")

    if conflicting:
        verdict = "CONFLICT"
    elif missing:
        verdict = "INSUFFICIENT_INFORMATION"
    elif equivalent:
        verdict = "EQUIVALENT"
    else:
        verdict = "SAME"

    total = len(critical) or 1
    attr_score = (len(matching) + 0.5 * len(equivalent)) / total
    if verdict == "CONFLICT":
        confidence = 0.0  # a confirmed conflict is not "somewhat confident" -- it's rejected
    elif embedding_similarity is not None:
        confidence = round(0.5 * embedding_similarity + 0.5 * attr_score, 4)
    else:
        confidence = round(attr_score, 4)

    return {
        "verdict": verdict,
        "confidence": confidence,
        "matching_attributes": matching,
        "conflicting_attributes": conflicting,
        "missing_attributes": missing,
        "equivalent_attributes": equivalent,
        "reasons": reasons,
        "embedding_similarity": embedding_similarity,
    }
