"""
Normalization pipeline (Phase 1): expand abbreviations and canonicalize units,
using Samanvay's own dictionaries. The dataset's own comment says it best:

  "The generator reads this LEFT->RIGHT to corrupt descriptions.
   The engine reads it RIGHT->LEFT to normalise them back."

So here we go right-to-left: any abbreviated/variant form found in text is
rewritten to its canonical phrase.
"""
import pathlib
import re

import yaml

DATASETS_ROOT = pathlib.Path(__file__).parent / "dictionaries"
ABBREV_PATH = DATASETS_ROOT / "abbreviations.yaml"
UNITS_PATH = DATASETS_ROOT / "units.yaml"


def _boundary(pattern: str) -> str:
    """Whole-token match that works even when the token contains '.', '"', '/'
    (plain \\b fails on those, since they're non-word characters on both sides)."""
    return rf'(?<![A-Za-z0-9])(?:{pattern})(?![A-Za-z0-9])'


def _load_abbrev_pairs() -> list[tuple[str, str]]:
    raw = yaml.safe_load(open(ABBREV_PATH))
    pairs = []
    for canonical, variants in raw.items():
        for variant in variants:
            pairs.append((variant, canonical))
    # longest variant first, so multi-word phrases ("gt vlv" -> "gate valve")
    # are rewritten before a shorter piece of them ("vlv" -> "valve") can fire.
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def _load_unit_pairs() -> list[tuple[str, str]]:
    raw = yaml.safe_load(open(UNITS_PATH))
    pairs = []
    for _, spec in raw.items():
        canonical = spec["canonical"]
        for variant in spec["variants"]:
            pairs.append((variant, canonical))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


_ABBREV_PAIRS = _load_abbrev_pairs()
_UNIT_PAIRS = _load_unit_pairs()


def _normalize_abbreviations_once(text: str) -> str:
    for variant, canonical in _ABBREV_PAIRS:
        pattern = _boundary(re.escape(variant))
        text = re.sub(pattern, canonical, text, flags=re.IGNORECASE)
    return text


def _normalize_units_once(text: str) -> str:
    for variant, canonical in _UNIT_PAIRS:
        escaped = re.escape(variant)
        # number directly attached or separated by whitespace: "50MM" / "50 M.M." -> "50 mm".
        # No lookbehind here: the preceding \d+ IS alphanumeric by design, so a
        # "not-preceded-by-alnum" check would wrongly reject the attached case ("130mm").
        numeric_pattern = rf'(\d+(?:\.\d+)?)\s*{escaped}(?![A-Za-z0-9])'
        text = re.sub(numeric_pattern, rf'\1 {canonical}', text, flags=re.IGNORECASE)
        # standalone occurrence with no adjacent number (rare, but keep it consistent)
        text = re.sub(_boundary(escaped), canonical, text, flags=re.IGNORECASE)
    return text


def normalize(description: str, max_passes: int = 3) -> str:
    """Some corruptions nest (e.g. "ball valve" -> "bl valve" -> "bl vv" during
    generation), so a single left-to-right pass can leave a partial expansion
    ("bl vv" -> "bl valve", stopping before "bl valve" -> "ball valve" is ever
    retried). Iterate to a fixed point instead."""
    if not description:
        return description
    text = description.strip()
    for _ in range(max_passes):
        before = text
        text = _normalize_units_once(text)
        text = _normalize_abbreviations_once(text)
        if text == before:
            break
    text = text.upper()
    text = " ".join(text.split())  # collapse repeated whitespace
    return text
