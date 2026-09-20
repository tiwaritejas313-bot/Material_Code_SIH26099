import { useEffect, useState } from "react";
import { downloadErpExport, getAuditTrail, listGroups } from "./api";
import { IconChevronDown } from "./Icons";
import { CnmcBanner, SourceTiles } from "./SharedUi";

function formatValue(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function AuditHistory({ commonCode }) {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getAuditTrail({ entityType: "common_material_group", entityId: commonCode })
      .then((d) => setEntries(d.items))
      .catch((e) => setError(e.message));
  }, [commonCode]);

  if (error) return <div className="error">{error}</div>;
  if (entries === null) return <p className="hint">Loading history...</p>;
  if (entries.length === 0)
    return (
      <p className="hint">
        No audit history for this group (it may predate audit logging).
      </p>
    );

  return (
    <div className="audit-history">
      <h4>Audit trail</h4>
      {entries.map((e) => (
        <div key={e._id} className="audit-row">
          <span className="audit-action">{e.action}</span>
          <span>by {e.actor}</span>
          <span className="audit-change">
            {formatValue(e.previous_value)} → {formatValue(e.new_value)}
          </span>
          {e.reason && <span className="audit-reason">— {e.reason}</span>}
          <span className="audit-time">
            {new Date(e.timestamp).toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function MaterialGroups() {
  const [groups, setGroups] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(null);

  function load() {
    setLoading(true);
    setError(null);
    listGroups({ limit: 100 })
      .then((d) => {
        setGroups(d.items);
        setTotal(d.total);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  return (
    <div className="material-groups">
      <div className="review-toolbar">
        <button onClick={load} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
        <span className="hint" style={{ margin: 0 }}>
          {total} active Common Material Group{total === 1 ? "" : "s"} (created
          via accepted review decisions -- Phase 6)
        </span>
      </div>

      <div className="erp-panel" style={{ marginTop: 16 }}>
        <h3 className="card-title">
          Export to ERP <span className="card-sub">Phase 9</span>
        </h3>
        <p className="hint" style={{ marginTop: 0 }}>
          Prototype SAP-style material-master extract (BUKRS/MATNR/MAKTX/MATKL +
          custom ZZ-prefixed harmonization fields) -- an{" "}
          <strong>integration-ready data contract</strong>, not a live SAP
          connection. Inbound: the Upload panel on the Explorer tab already
          accepts genuine SAP field names (BUKRS/MATNR/MAKTX/WERKS/MEINS)
          through the same tested ingestion pipeline.
        </p>
        <div className="erp-buttons">
          <button
            className="erp-btn"
            onClick={() =>
              downloadErpExport("csv").catch((e) => setError(e.message))
            }
          >
            Download CSV
          </button>
          <button
            className="erp-btn outline"
            onClick={() =>
              downloadErpExport("json").catch((e) => setError(e.message))
            }
          >
            View JSON
          </button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {!loading && groups.length === 0 && (
        <p className="hint">
          No groups yet -- accept a pair in the Review Queue to create the first
          one.
        </p>
      )}

      {groups.map((g) => {
        const isOpen = expanded === g.common_code;
        return (
          <div key={g.common_code} className="group-card">
            <div
              className="group-card-header"
              onClick={() => setExpanded(isOpen ? null : g.common_code)}
            >
              <CnmcBanner compact code={g.common_code} />
              <div className="group-card-main">
                <span className="group-desc">{g.canonical_description}</span>
                <span className="group-category">{g.category}</span>
              </div>
              <span className="group-member-count">
                {g.members.length} CPSE code{g.members.length === 1 ? "" : "s"}
              </span>
              <IconChevronDown className={isOpen ? "chev open" : "chev"} />
            </div>
            {isOpen && (
              <div className="group-card-body">
                <div className="std-desc">
                  <div className="std-desc-label">Standardized Description</div>
                  {g.canonical_description}
                </div>
                <SourceTiles members={g.members} />
                <AuditHistory commonCode={g.common_code} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
