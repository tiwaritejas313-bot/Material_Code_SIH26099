"""
Phase 1 ingestion: parse an uploaded CPSE material-master file (CSV or Excel)
into the record schema, tolerating the handful of column-naming conventions
we've actually seen across the PS-specific sample datasets (Samanvay uses
"legacy_code"/"description"; catalyst/materialsync use "material_code" or
"raw_description"; nmi_ai uses "Material_Code"/"Material_Description").

Phase 9 note: this also recognizes real SAP material-master field names
(MATNR, MAKTX, WERKS, BUKRS, MEINS -- the standard MARA/MAKT/MARC column
names), so a genuine SAP flat-file extract ingests through this exact same
tested path rather than needing a second, parallel import implementation.
This is the honest scope of "ERP integration" for a prototype: the data
CONTRACT is real, there is no live SAP connection behind it.
"""
import io

import pandas as pd

COLUMN_ALIASES: dict[str, list[str]] = {
    "cpse": ["cpse", "source_cpse", "bukrs"],
    "legacy_code": ["legacy_code", "material_code", "legacy_material_code", "source_material_code", "matnr"],
    "description": ["description", "material_description", "raw_description", "source_description", "maktx"],
    "plant": ["plant", "werks"],
    "uom": ["uom", "unit", "unit_of_measure", "source_uom", "meins"],
}
REQUIRED_FIELDS = ["cpse", "legacy_code", "description"]


class IngestionError(Exception):
    pass


def _normalize_header(col: str) -> str:
    return str(col).strip().lower().replace(" ", "_")


def _resolve_columns(columns: list[str]) -> dict[str, str]:
    """Map our canonical field name -> the actual column name present in the file."""
    normalized = {_normalize_header(c): c for c in columns}
    resolved = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                resolved[field] = normalized[alias]
                break
    return resolved


def parse_upload(filename: str, content: bytes) -> pd.DataFrame:
    lower = filename.lower()
    try:
        if lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise IngestionError(f"Unsupported file type: {filename} (use .csv, .xlsx, or .xls)")
    except IngestionError:
        raise
    except Exception as e:
        raise IngestionError(f"Could not parse {filename}: {e}")

    resolved = _resolve_columns(list(df.columns))

    # Some real exports (e.g. one file per CPSE) never put the CPSE name in a
    # column at all -- it's implied by the filename. Fall back to that instead
    # of failing the whole upload.
    inferred_cpse = None
    if "cpse" not in resolved:
        inferred_cpse = filename.rsplit(".", 1)[0].strip()

    missing = [f for f in REQUIRED_FIELDS if f not in resolved and not (f == "cpse" and inferred_cpse)]
    if missing:
        raise IngestionError(
            f"{filename}: missing required column(s) {missing}. "
            f"Found columns: {list(df.columns)}. "
            f"Accepted names per field: { {f: COLUMN_ALIASES[f] for f in missing} }"
        )

    out = pd.DataFrame()
    for field, actual_col in resolved.items():
        out[field] = df[actual_col]
    if "cpse" not in out.columns:
        out["cpse"] = inferred_cpse
    for field in ("plant", "uom"):
        if field not in out.columns:
            out[field] = None

    out = out.dropna(subset=["cpse", "legacy_code", "description"])
    out["cpse"] = out["cpse"].astype(str).str.strip()
    out["legacy_code"] = out["legacy_code"].astype(str).str.strip()
    out["description"] = out["description"].astype(str).str.strip()
    # object-dtype NaN (not Python None) can appear here depending on pandas's
    # column-creation path -- normalize it now so it never reaches JSON encoding.
    out = out.astype(object).where(out.notnull(), None)
    return out.reset_index(drop=True)
