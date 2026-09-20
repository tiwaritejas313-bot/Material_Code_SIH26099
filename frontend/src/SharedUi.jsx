// Shared presentational pieces used by several screens, so the "match result"
// card and the "generated CNMC" banner look identical everywhere:
//   - App.jsx (Explorer)      - ReviewQueue.jsx
//   - MaterialGroups.jsx      - LegacyMapping.jsx
// Nothing in here talks to the API; it only renders props.
import { useState } from "react";
import { IconAlert, IconArrowRight, IconCheck, IconChevronDown, IconX } from "./Icons";

// ---------------------------------------------------------------- CPSE colours

const CPSE_COLORS = {
  IOCL: "#d9382b",
  ONGC: "#ef8a1c",
  BPCL: "#d29500",
  HPCL: "#7a4ad8",
  GAIL: "#0f8b8d",
  NTPC: "#2f6fdb",
  SAIL: "#c2417a",
};
const FALLBACK_COLORS = ["#2f6fdb", "#0f8b8d", "#c2417a", "#7a4ad8", "#4f7a28", "#b45309", "#0e7490", "#9333ea"];

// Known public-sector names get a fixed brand-like colour; anything else gets
// a stable colour derived from the name so it never changes between renders.
export function cpseColor(name) {
  const key = String(name || "").trim().toUpperCase();
  for (const [known, color] of Object.entries(CPSE_COLORS)) {
    if (key === known || key.startsWith(known)) return color;
  }
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return FALLBACK_COLORS[h % FALLBACK_COLORS.length];
}

// ---------------------------------------------------------------- page header

export function PageHead({ num, title, subtitle, right }) {
  return (
    <div className="page-head">
      <div className="num-badge">{num}</div>
      <div className="page-head-text">
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {right && <div className="page-head-right">{right}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- match result

function MaterialCard({ label, record }) {
  return (
    <div className="material-card">
      <div className="material-card-head">{label} ({record.cpse})</div>
      <div className="material-card-body">
        <div className="material-code">{record.legacy_code}</div>
        {record.description && <div className="material-desc">{record.description}</div>}
      </div>
    </div>
  );
}

// Material A | Match Result | Material B, followed by the attribute table.
// `conflicting` is the list of {attribute, ...} objects and `missing` the list
// of attribute names, exactly as returned by the evaluate / review-queue APIs.
export function MatchVerdict({
  recordA,
  recordB,
  verdict,
  confidence,
  similarity,
  conflicting = [],
  missing = [],
  reasons = [],
  embedded = false,
  defaultOpen = true,
}) {
  const [open, setOpen] = useState(defaultOpen);
  const attrsA = recordA.attributes || {};
  const attrsB = recordB.attributes || {};
  const attrs = Object.keys({ ...attrsA, ...attrsB });
  const sim = typeof similarity === "number" ? similarity.toFixed(2) : null;

  return (
    <div className={`match-card verdict-${verdict}${embedded ? " embedded" : ""}`}>
      <div className="match-grid">
        <MaterialCard label="Material A" record={recordA} />

        <div className="match-center">
          <div className="match-center-title">Match Result</div>
          <div className={`verdict-pill verdict-pill-${verdict}`}>{String(verdict).replace(/_/g, " ")}</div>
          {sim && <div className="match-sim">Similarity: <strong>{sim}</strong></div>}
          {confidence && <div className="match-conf">confidence: {confidence}</div>}
          <button type="button" className="btn-outline" onClick={() => setOpen((o) => !o)}>
            {open ? "Hide" : "View"} Attribute Comparison
          </button>
        </div>

        <MaterialCard label="Material B" record={recordB} />
      </div>

      {open && (
        <div className="attr-compare">
          <div className="attr-compare-title">Attribute Comparison</div>
          <table className="verdict-attr-table">
            <thead>
              <tr>
                <th>Attribute</th>
                <th>Material A</th>
                <th>Material B</th>
                <th className="col-match">Match</th>
              </tr>
            </thead>
            <tbody>
              {attrs.map((attr) => {
                const isConflict = conflicting.some((c) => c.attribute === attr);
                const isMissing = missing.includes(attr);
                const rowClass = isConflict ? "attr-conflict" : isMissing ? "attr-missing" : "attr-match";
                return (
                  <tr key={attr} className={rowClass}>
                    <td>{attr}</td>
                    <td>{attrsA[attr] ?? "—"}</td>
                    <td>{attrsB[attr] ?? "—"}</td>
                    <td className="col-match">
                      {isConflict ? (
                        <span className="match-icon bad" title="Conflict"><IconX width={15} height={15} strokeWidth={2.6} /></span>
                      ) : isMissing ? (
                        <span className="match-icon warn" title="Missing on one side"><IconAlert width={15} height={15} strokeWidth={2.2} /></span>
                      ) : (
                        <span className="match-icon ok" title="Match"><IconCheck width={15} height={15} strokeWidth={2.8} /></span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {reasons.length > 0 && (
        <ul className="verdict-reasons">
          {reasons.map((reason, i) => <li key={i}>{reason}</li>)}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- CNMC pieces

// Green banner with the Common National Material Code. Pass onAction +
// actionLabel to show the white "View Traceability" style button.
export function CnmcBanner({ code, compact = false, actionLabel, onAction }) {
  return (
    <div className={`cnmc-banner${compact ? " compact" : ""}`}>
      <div>
        <div className="cnmc-label">Common National Material Code</div>
        <div className="cnmc-code">{code}</div>
      </div>
      {onAction && (
        <button type="button" className="btn-banner" onClick={onAction}>
          {actionLabel} <IconArrowRight width={15} height={15} />
        </button>
      )}
    </div>
  );
}

// Collapsible list of every original CPSE code that maps to one common code,
// one colour-coded tile per record. `members` is group.members from the API.
export function SourceTiles({ members }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="source-tiles-wrap">
      <button type="button" className="source-tiles-head" onClick={() => setOpen((o) => !o)}>
        <span>Mapped Source Codes ({members.length})</span>
        <IconChevronDown className={open ? "chev open" : "chev"} />
      </button>
      {open && (
        <div className="source-tiles">
          {members.map((m) => (
            <div key={m.record_id} className="source-tile" style={{ background: cpseColor(m.cpse) }}>
              <span className="tile-cpse">{m.cpse}</span>
              <span className="tile-code">{m.legacy_code}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
