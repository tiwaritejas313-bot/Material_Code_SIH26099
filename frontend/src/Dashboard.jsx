import { useEffect, useState } from "react";
import { getDashboardBreakdown, getDashboardSummary } from "./api";

// `tone` (optional): "critical" | "warning" recolours the bars so a chart of
// problems reads as a problem chart, not a neutral one.
function BarList({ data, total, unitLabel, tone }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = entries.length ? entries[0][1] : 1;
  return (
    <div className="bar-list">
      {entries.map(([label, value]) => (
        <div
          className="bar-row"
          key={label}
          title={`${value.toLocaleString()} ${unitLabel || ""}`}
        >
          <span className="bar-label">{label || "unclassified"}</span>
          <div className="bar-track">
            <div
              className={`bar-fill${tone ? ` tone-${tone}` : ""}`}
              style={{ width: `${(value / max) * 100}%` }}
            />
          </div>
          <span className="bar-value">
            {value.toLocaleString()}
            {total ? (
              <span className="bar-pct">
                {" "}
                ({((value / total) * 100).toFixed(1)}%)
              </span>
            ) : null}
          </span>
        </div>
      ))}
    </div>
  );
}

function StatTile({ value, label, tone }) {
  return (
    <div className={`stat-card${tone ? ` tone-${tone}` : ""}`}>
      <div className="stat-value">
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    setLoading(true);
    setError(null);
    getDashboardSummary()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  function loadBreakdown() {
    getDashboardBreakdown()
      .then(setBreakdown)
      .catch((e) => setError(e.message));
  }

  if (error) return <div className="error">{error}</div>;
  if (!data)
    return <p className="hint">{loading ? "Loading dashboard..." : ""}</p>;

  const {
    action_required,
    processed,
    data_quality,
    technical_conflicts_by_category,
    match_status_method,
  } = data;

  return (
    <div className="dashboard">
      <div className="review-toolbar">
        <button onClick={load} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
        <span className="hint" style={{ margin: 0 }}>
          Every number below is a live query -- nothing cached or precomputed.
        </span>
      </div>

      <div className="dashboard-panel dashboard-panel-action">
        <h3 className="card-title">What needs my attention?</h3>
        <section className="stats">
          <StatTile
            value={action_required.pending_review}
            label="pending review (total)"
            tone="warning"
          />
          <StatTile
            value={action_required.pending_conflicts}
            label="technical conflicts, unreviewed"
            tone="critical"
          />
          <StatTile
            value={action_required.pending_insufficient_information}
            label="insufficient information, unreviewed"
            tone="warning"
          />
        </section>
        <p className="method-note">{match_status_method}</p>
      </div>

      <div className="dashboard-panel">
        <h3 className="card-title">What has been processed?</h3>
        <section className="stats">
          <StatTile value={processed.total_records} label="total records" />
          <StatTile
            value={processed.approved_material_groups}
            label="approved material groups"
            tone="good"
          />
          <StatTile
            value={processed.mapped_to_a_common_code}
            label="records mapped to a common code"
            tone="good"
          />
          <StatTile
            value={processed.decisions_accepted}
            label="decisions: accepted"
            tone="good"
          />
          <StatTile
            value={processed.decisions_rejected}
            label="decisions: rejected"
            tone="critical"
          />
          <StatTile
            value={processed.decisions_escalated}
            label="decisions: escalated"
            tone="warning"
          />
        </section>
      </div>

      <div className="dashboard-panel">
        <h3 className="card-title">
          Where are the problems? <span className="card-sub">Data quality</span>
        </h3>
        <section className="stats">
          <StatTile
            value={data_quality.missing_critical_attributes}
            label="records missing a critical attribute"
            tone="warning"
          />
          <StatTile
            value={data_quality.unclassified_category}
            label="records with unrecognized category"
            tone="warning"
          />
          <StatTile
            value={data_quality.duplicate_legacy_code_groups}
            label="duplicate original-code groups"
            tone="critical"
          />
          <StatTile
            value={data_quality.empty_description}
            label="records with empty description"
            tone={data_quality.empty_description ? "critical" : "good"}
          />
        </section>
        {Object.keys(data_quality.missing_attribute_breakdown || {}).length >
          0 && (
          <>
            <h4>Missing attributes, by field</h4>
            <BarList
              data={data_quality.missing_attribute_breakdown}
              unitLabel="records"
              tone="warning"
            />
          </>
        )}
        <p className="method-note">{data_quality.note}</p>
      </div>

      {Object.keys(technical_conflicts_by_category || {}).length > 0 && (
        <div className="dashboard-panel">
          <h3 className="card-title">Technical conflicts by category</h3>
          <BarList
            data={technical_conflicts_by_category}
            unitLabel="conflicts"
            tone="critical"
          />
        </div>
      )}

      <div className="dashboard-panel">
        <button
          className="find-candidates-btn"
          onClick={() => {
            setShowBreakdown((s) => !s);
            if (!showBreakdown) loadBreakdown();
          }}
        >
          {showBreakdown ? "Hide" : "Show"} records-by-CPSE / by-category
          breakdown
        </button>
        {showBreakdown && breakdown && (
          <>
            <h4>Records by CPSE</h4>
            <BarList
              data={breakdown.by_cpse}
              total={processed.total_records}
              unitLabel="records"
            />
            <h4>Records by category</h4>
            <BarList
              data={breakdown.by_category}
              total={processed.total_records}
              unitLabel="records"
            />
          </>
        )}
      </div>
    </div>
  );
}
