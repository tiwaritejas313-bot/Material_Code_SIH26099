"""
Phase 2: category classification + structured attribute extraction.

All extraction runs against `normalized_description` (Phase 1's output), never
against category_true / the raw description — a production system won't have
category_true, and Samanvay's own generator comment is explicit that "the
engine must recover attributes from text alone."

Value pools and hard-attribute lists below are taken directly from
sih26099_datasets/.../samanvay_synthetic_12k_clusters/categories.py, verified
against the real generator rather than guessed.
"""
import re

# category -> the fixed head-noun phrase that always opens its description,
# after normalization (canonical spelling, uppercase). Longer/more specific
# phrases are checked first so e.g. "CHECK VALVE" doesn't get missed inside a
# generic "VALVE" scan, and CAF/spiral gasket don't collide.
HEAD_PHRASES: list[tuple[str, str]] = [
    ("caf_gasket", "COMPRESSED ASBESTOS FIBRE GASKET"),
    ("wnrf_flange", "WELD NECK RAISED FACE FLANGE"),
    ("spiral_gasket", "SPIRAL WOUND GASKET"),
    ("xlpe_cable", "XLPE ARMOURED CABLE"),
    ("induction_motor", "INDUCTION MOTOR"),
    ("centrifugal_pump", "CENTRIFUGAL PUMP"),
    ("roller_bearing", "ROLLER BEARING"),
    ("hexagonal_bolt_std", "HEXAGONAL BOLT"),   # placeholder overwritten below; kept for length-sort clarity
    ("stud_bolt", "STUD BOLT"),
    ("hex_bolt", "HEXAGONAL BOLT"),
    ("hex_nut", "HEXAGONAL NUT"),
    ("plain_washer", "PLAIN WASHER"),
    ("spring_washer", "SPRING WASHER"),
    ("ball_bearing", "BALL BEARING"),
    ("check_valve", "CHECK VALVE"),
    ("gate_valve", "GATE VALVE"),
    ("globe_valve", "GLOBE VALVE"),
    ("ball_valve", "BALL VALVE"),
    ("seamless_pipe", "SEAMLESS PIPE"),
    ("elbow_90", "ELBOW 90 DEGREE"),
    ("o_ring", "O-RING"),
]
HEAD_PHRASES = [p for p in HEAD_PHRASES if p[0] != "hexagonal_bolt_std"]
HEAD_PHRASES.sort(key=lambda p: len(p[1]), reverse=True)

# Verified directly from categories.py's `hard` field per category.
HARD_ATTRIBUTES: dict[str, list[str]] = {
    "hex_bolt": ["thread", "length", "material"],
    "hex_nut": ["thread", "material"],
    "stud_bolt": ["thread", "length", "material"],
    "plain_washer": ["thread", "material"],
    "spring_washer": ["thread", "material"],
    "gate_valve": ["bore", "pclass", "material"],
    "globe_valve": ["bore", "pclass", "material"],
    "ball_valve": ["bore", "pclass", "material"],
    "check_valve": ["bore", "pclass", "material"],
    "ball_bearing": ["desig", "seal"],
    "roller_bearing": ["desig"],
    "spiral_gasket": ["bore", "pclass", "material"],
    "caf_gasket": ["bore", "thickness"],
    "seamless_pipe": ["bore", "sched", "material"],
    "elbow_90": ["bore", "sched", "material"],
    "wnrf_flange": ["bore", "pclass", "material"],
    "xlpe_cable": ["cores", "csa", "kv"],
    "induction_motor": ["kw", "rpm"],
    "centrifugal_pump": ["cap", "head", "material"],
    "o_ring": ["idm", "cs", "material"],
}

# Union of every material value pool in categories.py (FAST_MAT, VBODY, PIPE_MAT,
# GSK_MAT, ELAST), longest phrase first so "STAINLESS STEEL 316 GRAPHITE" is
# tried before the shorter "STAINLESS STEEL 316" swallows part of it.
MATERIAL_VALUES = sorted(
    {
        "STAINLESS STEEL 304", "STAINLESS STEEL 316", "MILD STEEL", "HIGH TENSILE 8.8",
        "GALVANISED IRON", "CARBON STEEL", "CAST IRON", "WCB", "A106 GR B",
        "STAINLESS STEEL 316 GRAPHITE", "STAINLESS STEEL 304 GRAPHITE",
        "COMPRESSED ASBESTOS FIBRE", "GRAPHITE",
        "NITRILE", "VITON", "EPDM", "SILICONE", "NEOPRENE",
    },
    key=len, reverse=True,
)


def classify_category(normalized_description: str) -> str | None:
    text = normalized_description or ""
    for category, phrase in HEAD_PHRASES:
        if phrase in text:
            return category
    return None


def _find(pattern: str, text: str, group: int = 1) -> str | None:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(group) if m else None


def _find_material(text: str) -> str | None:
    for value in MATERIAL_VALUES:
        if value in text:
            return value
    return None


def extract_attributes(category: str, normalized_description: str) -> dict[str, str | None]:
    t = normalized_description or ""
    attrs: dict[str, str | None] = {}

    if category in ("hex_bolt", "stud_bolt"):
        attrs["thread"] = _find(r"\bM(\d{1,2})\b", t) and f"M{_find(r'M(\d{1,2})', t)}"
        length_mm = _find(r"X\s*(\d+(?:\.\d+)?)\s*MM\b", t)
        if length_mm is None:
            # units.yaml canonicalizes cm *spelling* but doesn't convert cm<->mm,
            # and Samanvay's own unit-corruption occasionally renders round mm
            # lengths in cm (e.g. 180mm -> "18 cm") -- convert back to mm here
            # so length comparisons stay in one unit.
            length_cm = _find(r"X\s*(\d+(?:\.\d+)?)\s*CM\b", t)
            length_mm = str(float(length_cm) * 10) if length_cm else None
        attrs["length"] = length_mm
        attrs["material"] = _find_material(t)
    elif category in ("hex_nut", "plain_washer", "spring_washer"):
        attrs["thread"] = _find(r"\bM(\d{1,2})\b", t) and f"M{_find(r'M(\d{1,2})', t)}"
        attrs["material"] = _find_material(t)
    elif category in ("gate_valve", "globe_valve", "ball_valve", "check_valve", "spiral_gasket", "wnrf_flange"):
        attrs["bore"] = _find(r"(\d+(?:\.\d+)?(?:/\d+)?)\s*INCH\b", t)
        attrs["pclass"] = _find(r"\bCLASS\s*(\d+)\b", t)
        attrs["material"] = _find_material(t)
        ends = _find(r"\b(FLANGED|SCREWED)\b", t)
        attrs["ends"] = ends
    elif category == "caf_gasket":
        attrs["bore"] = _find(r"(\d+(?:\.\d+)?(?:/\d+)?)\s*INCH\b", t)
        # thickness is the OTHER mm-figure in the description (not a length/bore figure)
        attrs["thickness"] = _find(r"(\d+(?:\.\d+)?)\s*MM\b", t)
    elif category in ("seamless_pipe", "elbow_90"):
        attrs["bore"] = _find(r"(\d+(?:\.\d+)?(?:/\d+)?)\s*INCH\b", t)
        attrs["sched"] = _find(r"\b(SCH\d+|XS)\b", t)
        attrs["material"] = _find_material(t)
    elif category == "ball_bearing":
        attrs["desig"] = _find(r"\b(6\d{3})\b", t)
        attrs["seal"] = _find(r"\b(2RS|ZZ|OPEN)\b", t)
    elif category == "roller_bearing":
        attrs["desig"] = _find(r"\b(NU\d{3}|2\d{4})\b", t)
    elif category == "xlpe_cable":
        attrs["cores"] = _find(r"(\d+(?:\.\d+)?)\s*CORE\b", t)
        attrs["csa"] = _find(r"(\d+(?:\.\d+)?)\s*SQMM\b", t)
        attrs["kv"] = _find(r"(\d+(?:\.\d+)?)\s*KV\b", t)
    elif category == "induction_motor":
        attrs["kw"] = _find(r"(\d+(?:\.\d+)?)\s*KW\b", t)
        attrs["rpm"] = _find(r"(\d+)\s*RPM\b", t)
    elif category == "centrifugal_pump":
        attrs["cap"] = _find(r"(\d+(?:\.\d+)?)\s*M3/HR\b", t)
        attrs["head"] = _find(r"HEAD\s+(\d+(?:\.\d+)?)\s*M\b", t)
        attrs["material"] = _find_material(t)
    elif category == "o_ring":
        attrs["idm"] = _find(r"(\d+(?:\.\d+)?)\s*MM\s+ID\b", t)
        attrs["cs"] = _find(r"(\d+(?:\.\d+)?)\s*MM\s+SECTION\b", t)
        attrs["material"] = _find_material(t)

    return attrs


def extract(normalized_description: str) -> dict:
    """Full Phase 2 output for one record: predicted category + its attributes,
    with missing-critical-attribute flags already computed for Phase 4 to use."""
    category = classify_category(normalized_description)
    if category is None:
        return {"category_predicted": None, "attributes": {}, "missing_critical": []}

    attrs = extract_attributes(category, normalized_description)
    hard = HARD_ATTRIBUTES.get(category, [])
    missing_critical = [a for a in hard if attrs.get(a) is None]
    return {
        "category_predicted": category,
        "attributes": attrs,
        "missing_critical": missing_critical,
    }
