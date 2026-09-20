import { useEffect, useState } from "react";
import { getDecisions, getReviewQueue, submitDecision } from "./api";
import { PageHead, CnmcBanner } from "./SharedUi";
import { IconCheck, IconSearch, IconX, IconAlert } from "./Icons";

// The pipeline stepper
function PipelineStepper() {
  const steps = ["Ingest", "Clean", "Extract", "Match", "Review", "Generate", "Export"];
  const currentStep = 4;
  return (
    <div className="pipeline-stepper">
      {steps.map((step, i) => (
        <div key={step} className={`step-item ${i < currentStep ? "completed" : i === currentStep ? "active" : "future"}`}>
          <div className="step-circle">{i < currentStep ? "✓" : i + 1}</div>
          <div className="step-label">{step}</div>
          {i < steps.length - 1 && <div className="step-line" />}
        </div>
      ))}
    </div>
  );
}

function MultiCandidateComparison({ sourceRecord, candidates }) {
  // Collect all unique attributes across the source record and all candidates
  const allAttrs = new Set(Object.keys(sourceRecord.attributes || {}));
  candidates.forEach(c => {
    Object.keys(c.record.attributes || {}).forEach(attr => allAttrs.add(attr));
  });
  
  const attrsArray = Array.from(allAttrs).sort();

  return (
    <div className="comparison-table-wrapper">
      <table className="enterprise-table">
        <thead>
          <tr>
            <th>Attribute</th>
            <th>Material 1 ({sourceRecord.cpse})</th>
            {candidates.map((c, i) => (
              <th key={c.record.record_id}>Material {i + 2} ({c.record.cpse})<br/><small style={{color: '#666', fontWeight: 'normal'}}>Sim Score: {c.embedding_similarity?.toFixed(2)}</small></th>
            ))}
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {attrsArray.map(attr => {
            const val1 = sourceRecord.attributes?.[attr];
            
            let hasMissing = false;
            let hasConflict = false;
            
            candidates.forEach(c => {
               const isMissing = c.missing_attributes?.includes(attr);
               const isConflict = c.conflicting_attributes?.some(ca => ca.attribute === attr);
               if (isMissing) hasMissing = true;
               if (isConflict) hasConflict = true;
            });
            
            return (
              <tr key={attr}>
                <td className="attr-name">{attr}</td>
                <td>{val1 || "—"}</td>
                {candidates.map(c => (
                  <td key={c.record.record_id}>{c.record.attributes?.[attr] || "—"}</td>
                ))}
                <td className="status-cell">
                  {hasConflict ? <span className="status-conflict">! Conflict</span> : 
                   hasMissing ? <span className="status-missing">? Not Available</span> : 
                   <span className="status-match">✓ Match</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function QueueGroup({ group, canReview, onDecided }) {
  const { source_record, candidates } = group;
  const [decision, setDecision] = useState(""); 
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [generatedGroup, setGeneratedGroup] = useState(null);

  async function handleSubmit() {
    if (!decision) {
      setError("Please select a decision.");
      return;
    }
    
    let action = decision;
    let targetCandidate = null;
    
    if (decision.startsWith("accept_")) {
      action = "accept";
      const idx = parseInt(decision.split("_")[1]);
      targetCandidate = candidates[idx];
    }
    
    if ((action === "reject" || action === "escalate") && !reason.trim()) {
      setError(`A reason is required to ${action}.`);
      return;
    }
    
    setSubmitting(true);
    setError(null);
    try {
      if (action === "accept") {
        const res = await submitDecision(source_record.record_id, targetCandidate.record.record_id, action, reason.trim() || null);
        setGeneratedGroup(res.group);
      } else {
        if (candidates.length > 0) {
            await submitDecision(source_record.record_id, candidates[0].record.record_id, action, reason.trim() || null);
        }
        onDecided();
      }
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }
  
  if (generatedGroup) {
     return (
        <div className="review-group-panel">
           <CnmcBanner code={generatedGroup.common_code} />
           <div className="rg-materials-cards" style={{marginTop: 16}}>
               <p>Match accepted successfully. The Common National Material Code has been updated.</p>
           </div>
           <button className="btn-primary" style={{marginTop: 16}} onClick={onDecided}>Next Item</button>
        </div>
     );
  }

  const selectedCandidateIdx = decision.startsWith("accept_") ? parseInt(decision.split("_")[1]) : null;
  const cnmcPreview = {
    desc: source_record.normalized_description || source_record.description,
    codes: [source_record]
  };
  if (selectedCandidateIdx !== null && candidates[selectedCandidateIdx]) {
     cnmcPreview.codes.push(candidates[selectedCandidateIdx].record);
  }

  return (
    <div className="review-group-panel">
      <div className="rg-header">
        <h2>Candidate Match ({candidates.length + 1} materials)</h2>
        <div className="rg-meta">
          <span>Match ID: M-{new Date().getFullYear()}-{source_record.record_id.slice(-6).toUpperCase()}</span>
          {candidates.length > 0 && <span>Max Similarity: {candidates[0].embedding_similarity?.toFixed(2)}</span>}
        </div>
      </div>
      
      <div className="rg-materials-cards">
        <div className="rg-card source-card">
          <h4>Material 1 ({source_record.cpse})</h4>
          <p className="rg-code">Original Code: {source_record.legacy_code}</p>
          <p className="rg-desc">Description: {source_record.description}</p>
        </div>
        {candidates.map((c, i) => (
          <div key={c.record.record_id} className="rg-card candidate-card">
            <h4>Material {i + 2} ({c.record.cpse})</h4>
            <p className="rg-code">Original Code: {c.record.legacy_code}</p>
            <p className="rg-desc">Description: {c.record.description}</p>
            <p className="rg-verdict" style={{marginTop: 8, fontSize: 12, fontWeight: 'bold'}}>
              {c.verdict === 'CONFLICT' && <span style={{color: '#d9382b'}}>Technical Conflict</span>}
              {c.verdict === 'INSUFFICIENT_INFORMATION' && <span style={{color: '#f26a21'}}>Insufficient Info</span>}
              {(c.verdict === 'SAME' || c.verdict === 'EQUIVALENT') && <span style={{color: '#1a8a4a'}}>Match</span>}
            </p>
          </div>
        ))}
      </div>
      
      <MultiCandidateComparison sourceRecord={source_record} candidates={candidates} />
      
      {canReview && (
        <div className="rg-decision-section">
          <div className="rg-decision-form">
            <h3>Your Decision</h3>
            <div className="rg-radio-group">
              {candidates.map((c, i) => (
                <label key={c.record.record_id} className="rg-radio">
                  <input type="radio" name={`dec-${source_record.record_id}`} checked={decision === `accept_${i}`} onChange={() => setDecision(`accept_${i}`)} />
                  <span>Accept Match with Material {i + 2} ({c.record.cpse})</span>
                </label>
              ))}
              <label className="rg-radio">
                <input type="radio" name={`dec-${source_record.record_id}`} checked={decision === "reject"} onChange={() => setDecision("reject")} />
                <span>Reject Match</span>
              </label>
              <label className="rg-radio">
                <input type="radio" name={`dec-${source_record.record_id}`} checked={decision === "escalate"} onChange={() => setDecision("escalate")} />
                <span>Escalate / Need More Info</span>
              </label>
            </div>
            
            <div className="rg-reason">
              <label>Reason (required)</label>
              <textarea 
                placeholder="e.g., attributes match, verified from specification, etc."
                value={reason}
                onChange={e => setReason(e.target.value)}
              />
            </div>
            
            {error && <div className="error-text">{error}</div>}
            
            <button className="btn-primary submit-btn" onClick={handleSubmit} disabled={submitting}>
              {submitting ? "Submitting..." : "Submit Decision"}
            </button>
          </div>
          
          <div className="rg-cnmc-preview">
             <h3>Generated CNMC (on approval)</h3>
             {selectedCandidateIdx !== null ? (
               <div className="cnmc-preview-box">
                 <div className="cp-code">CNMC-PENDING</div>
                 <div className="cp-desc">Standardized Description:<br/><strong>{cnmcPreview.desc}</strong></div>
                 <div className="cp-mapped">
                   Mapped Source Codes:
                   <ul>
                     {cnmcPreview.codes.map((rc, idx) => (
                       <li key={idx}>{rc.cpse}: {rc.legacy_code}</li>
                     ))}
                   </ul>
                 </div>
                 <div className="cp-notice">This CNMC will be created after you approve this match.</div>
               </div>
             ) : (
               <div className="cnmc-empty">
                 Select an "Accept Match" option to preview the resulting CNMC.
               </div>
             )}
          </div>
        </div>
      )}
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
    getReviewQueue({ limit: 10, source: source || undefined })
      .then((data) => setQueue(data.queue))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  function loadHistory() {
    getDecisions(50).then((d) => setDecisions(d.items)).catch((err) => setError(err.message));
  }

  useEffect(() => {
    loadQueue();
    loadHistory();
  }, [source]);

  function handleDecided(index) {
    setQueue((prev) => prev.filter((_, i) => i !== index));
    loadHistory();
  }

  // Calculate dynamic stats
  let totalPending = queue.length;
  let conflicts = 0;
  let insufficientInfo = 0;
  queue.forEach(group => {
    group.candidates.forEach(c => {
      if (c.verdict === "CONFLICT") conflicts++;
      if (c.verdict === "INSUFFICIENT_INFORMATION") insufficientInfo++;
    });
  });

  return (
    <div className="enterprise-page">
      <PipelineStepper />
      
      <div className="page-header">
        <div>
          <h1>Reviewer Queue</h1>
          <p className="page-subtitle">Review AI-suggested material matches and make a decision.</p>
        </div>
        <div className="header-actions">
          <input
            type="text"
            className="search-input"
            placeholder="Search by code or description..."
            value={source}
            onChange={(e) => setSource(e.target.value)}
          />
          <button className="btn-outline" onClick={loadQueue} disabled={loading}>
            {loading ? "Loading..." : "Filter"}
          </button>
          <button className="btn-outline" onClick={() => setShowHistory((s) => !s)}>
            {showHistory ? "Hide history" : "Show decision history"}
          </button>
        </div>
      </div>

      <div className="queue-stats">
         <span className="stat-pill pending">Pending review groups: {totalPending}</span>
         <span className="stat-pill conflict">Technical conflicts: {conflicts}</span>
         <span className="stat-pill warning">Insufficient info: {insufficientInfo}</span>
         <span className="stat-pill done">Recently reviewed: {decisions.length}</span>
      </div>

      {showHistory && (
        <div className="decision-history" style={{marginBottom: 32, background: '#fff', padding: 24, border: '1px solid #e2e7f1', borderRadius: 6}}>
          <h3 style={{marginTop: 0}}>Decision history</h3>
          {decisions.length === 0 && <p className="hint">No decisions recorded yet.</p>}
          <table className="enterprise-table">
             <thead>
                <tr>
                   <th>System Verdict</th>
                   <th>Reviewer Action</th>
                   <th>Reviewer</th>
                   <th>Reason</th>
                   <th>Time</th>
                </tr>
             </thead>
             <tbody>
               {decisions.map((d) => (
                 <tr key={d._id}>
                   <td>{d.system_verdict}</td>
                   <td><strong style={{color: d.action === 'accept' ? '#1a8a4a' : d.action === 'reject' ? '#d9382b' : '#f26a21'}}>{d.action.toUpperCase()}</strong></td>
                   <td>{d.reviewer}</td>
                   <td>{d.reason || "—"}</td>
                   <td>{new Date(d.decided_at).toLocaleString()}</td>
                 </tr>
               ))}
             </tbody>
          </table>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      {!loading && queue.length === 0 && (
        <div className="empty-state">Queue is empty — nothing pending review right now.</div>
      )}

      <div className="queue-list">
        {queue.map((group, i) => (
          <QueueGroup 
            key={group.source_record.record_id} 
            group={group} 
            canReview={canReview} 
            onDecided={() => handleDecided(i)} 
          />
        ))}
      </div>
    </div>
  );
}
