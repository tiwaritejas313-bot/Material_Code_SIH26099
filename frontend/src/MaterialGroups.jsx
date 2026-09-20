import { useEffect, useState } from "react";
import { downloadErpExport, getAuditTrail, listGroups } from "./api";

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
  if (entries.length === 0) return <p className="hint">No audit history for this group (it may predate audit logging).</p>;

  return (
    <div className="audit-history">
      <h4>Audit trail</h4>
      {entries.map((e) => (
        <div key={e._id} className="audit-row">
          <span className="audit-action">{e.action}</span>
          <span>by {e.actor}</span>
          <span className="audit-change">{formatValue(e.previous_value)} → {formatValue(e.new_value)}</span>
          {e.reason && <span className="audit-reason">— {e.reason}</span>}
          <span className="audit-time">{new Date(e.timestamp).toLocaleString()}</span>
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
      .then((d) => { setGroups(d.items); setTotal(d.total); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  return (
    <div className="material-groups">
      <div className="review-toolbar">
        <button onClick={load} disabled={loading}>{loading ? "Loading..." : "Refresh"}</button>
        <span className="hint">{total} active Common Material Group{total === 1 ? "" : "s"} (created via accepted review decisions -- Phase 6)</span>
      </div>

      <div className="erp-panel">
        <h3>Export to ERP (Phase 9)</h3>
        <p className="hint">
          Prototype SAP-style material-master extract (BUKRS/MATNR/MAKTX/MATKL + custom ZZ-prefixed
          harmonization fields) -- an <strong>integration-ready data contract</strong>, not a live SAP
          connection. Inbound: the Upload panel on the Explorer tab already accepts genuine SAP field
          names (BUKRS/MATNR/MAKTX/WERKS/MEINS) through the same tested ingestion pipeline.
        </p>
        <div className="erp-buttons">
          <button className="erp-btn" onClick={() => downloadErpExport("csv").catch((e) => setError(e.message))}>Download CSV</button>
          <button className="erp-btn" onClick={() => downloadErpExport("json").catch((e) => setError(e.message))}>View JSON</button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {!loading && groups.length === 0 && (
        <p className="hint">No groups yet -- accept a pair in the Review Queue to create the first one.</p>
      )}

      {groups.map((g) => {
        const isOpen = expanded === g.common_code;
        return (
          <div key={g.common_code} className="group-card">
            <div className="group-card-header" onClick={() => setExpanded(isOpen ? null : g.common_code)}>
              <span className="common-code">{g.common_code}</span>
              <span className="group-category">{g.category}</span>
              <span className="group-desc">{g.canonical_description}</span>
              <span className="group-member-count">{g.members.length} CPSE code{g.members.length === 1 ? "" : "s"}</span>
            </div>
            {isOpen && (
              <>
                <table className="group-members-table">
                  <thead>
                    <tr><th>CPSE</th><th>Original (legacy) code</th></tr>
                  </thead>
                  <tbody>
                    {g.members.map((m) => (
                      <tr key={m.record_id}>
                        <td>{m.cpse}</td>
                        <td>{m.legacy_code}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <AuditHistory commonCode={g.common_code} />
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
