import { useEffect, useState } from "react";
import { getDecisions, getReviewQueue, submitDecision } from "./api";

function AttributeComparison({ recordA, recordB, conflicting, missing }) {
  const attrs = Object.keys({ ...recordA.attributes, ...recordB.attributes });
  return (
    <table className="verdict-attr-table">
      <thead>
        <tr>
          <th>Attribute</th>
          <th>{recordA.legacy_code} ({recordA.cpse})</th>
          <th>{recordB.legacy_code} ({recordB.cpse})</th>
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
              <td>{recordA.attributes[attr] ?? "—"}</td>
              <td>{recordB.attributes[attr] ?? "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function QueueItem({ item, canReview, onDecided }) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(null);
  const [error, setError] = useState(null);

  async function decide(action) {
    if ((action === "reject" || action === "escalate") && !reason.trim()) {
      setError(`A reason is required to ${action} a match.`);
      return;
    }
    setSubmitting(action);
    setError(null);
    try {
      // No reviewer argument -- the backend derives identity from the signed-in
      // session's JWT, not a free-text field.
      await submitDecision(item.record_a.record_id, item.record_b.record_id, action, reason.trim() || null);
      onDecided();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className={`verdict-panel verdict-${item.verdict}`}>
      <div className="verdict-header">
        <span className="verdict-badge">{item.verdict}</span>
        <span className="verdict-confidence">confidence: {item.confidence}</span>
        <span className="verdict-confidence">embedding sim: {item.embedding_similarity?.toFixed(3)}</span>
      </div>
      <div className="queue-descriptions">
        <div><strong>A ({item.record_a.cpse}/{item.record_a.legacy_code}):</strong> {item.record_a.description}</div>
        <div><strong>B ({item.record_b.cpse}/{item.record_b.legacy_code}):</strong> {item.record_b.description}</div>
      </div>
      <AttributeComparison
        recordA={item.record_a}
        recordB={item.record_b}
        conflicting={item.conflicting_attributes}
        missing={item.missing_attributes}
      />
      <ul className="verdict-reasons">
        {item.reasons.map((r, i) => <li key={i}>{r}</li>)}
      </ul>
      {canReview ? (
        <div className="decision-controls">
          <input
            type="text"
            placeholder="reason (required for reject/escalate)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button className="decision-btn accept" disabled={!!submitting} onClick={() => decide("accept")}>
            {submitting === "accept" ? "..." : "Accept"}
          </button>
          <button className="decision-btn reject" disabled={!!submitting} onClick={() => decide("reject")}>
            {submitting === "reject" ? "..." : "Reject"}
          </button>
          <button className="decision-btn escalate" disabled={!!submitting} onClick={() => decide("escalate")}>
            {submitting === "escalate" ? "..." : "Escalate"}
          </button>
        </div>
      ) : (
        <p className="hint">Viewers can inspect matches but not decide on them.</p>
      )}
      {error && <div className="error">{error}</div>}
    </div>
  );
}

export default function ReviewQueue({ canReview }) {
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [source, setSource] = useState("");

  function loadQueue() {
    setLoading(true);
    setError(null);
    // Without a source filter this scans records in roughly insertion order --
    // tens of thousands of pre-loaded benchmark records were inserted long
    // before any real upload, so a freshly-uploaded file's own rows would
    // never be reached. Filtering by source points the scan at just that file.
    getReviewQueue({ limit: 15, source: source || undefined })
      .then((data) => setQueue(data.queue))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(loadQueue, [source]);

  function loadHistory() {
    getDecisions(50).then((d) => setDecisions(d.items)).catch((err) => setError(err.message));
  }

  function handleDecided(index) {
    setQueue((prev) => prev.filter((_, i) => i !== index));
  }

  return (
    <div className="review-queue">
      <div className="review-toolbar">
        <input
          type="text"
          placeholder="filter by source (e.g. sample_upload.csv) -- blank scans the whole database"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          style={{ minWidth: 320 }}
        />
        <button onClick={loadQueue} disabled={loading}>{loading ? "Loading..." : "Refresh queue"}</button>
        <button onClick={() => { setShowHistory((s) => !s); if (!showHistory) loadHistory(); }}>
          {showHistory ? "Hide history" : "Show decision history"}
        </button>
      </div>
      <p className="hint">
        Without a source filter, the queue scans records in roughly insertion order -- with the large
        pre-loaded benchmark dataset inserted long before any real upload, your own uploaded rows won't
        surface unless you filter by their source/filename here.
      </p>

      {error && <div className="error">{error}</div>}

      {showHistory && (
        <div className="decision-history">
          <h3>Decision history</h3>
          {decisions.length === 0 && <p className="hint">No decisions recorded yet.</p>}
          {decisions.map((d) => (
            <div key={d._id} className={`history-row action-${d.action}`}>
              <span className="history-verdict">{d.system_verdict}</span>
              <span className="history-action">{d.action}</span>
              <span>by {d.reviewer}</span>
              {d.reason && <span className="history-reason">— {d.reason}</span>}
              <span className="history-time">{new Date(d.decided_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}

      {!loading && queue.length === 0 && <p className="hint">Queue is empty -- nothing pending review right now.</p>}

      {queue.map((item, i) => (
        <QueueItem key={`${item.record_a.record_id}-${item.record_b.record_id}`} item={item} canReview={canReview} onDecided={() => handleDecided(i)} />
      ))}
    </div>
  );
}
