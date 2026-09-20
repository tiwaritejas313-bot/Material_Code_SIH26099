import { Fragment, useEffect, useRef, useState } from "react";
import { evaluatePair, getCandidates, getHealth, getRecordGroup, getRecordStats, getStoredUser, listRecords, logout, setUnauthorizedHandler, uploadRecords } from "./api";
import Dashboard from "./Dashboard";
import { IconChart, IconChecklist, IconGrid, IconLink, IconLogout, IconSearch } from "./Icons";
import LegacyMapping from "./LegacyMapping";
import Login from "./Login";
import MaterialGroups from "./MaterialGroups";
import ReviewQueue from "./ReviewQueue";
import "./App.css";

const NAV_ITEMS = [
  { key: "explorer", label: "Material Explorer", icon: IconGrid },
  { key: "review", label: "Review Queue", icon: IconChecklist },
  { key: "groups", label: "Material Groups", icon: IconLink },
  { key: "dashboard", label: "Dashboard", icon: IconChart },
  { key: "legacy", label: "Legacy Mapping", icon: IconSearch },
];

const PAGE_SIZE = 20;

function App() {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [source, setSource] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [uploadSource, setUploadSource] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [candidatesById, setCandidatesById] = useState({});
  const [candidatesLoading, setCandidatesLoading] = useState(null);
  const [candidatesError, setCandidatesError] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [evaluationError, setEvaluationError] = useState(null);
  const [activeTab, setActiveTab] = useState("explorer");
  const [groupById, setGroupById] = useState({});
  const [groupLoading, setGroupLoading] = useState(null);
  const fileInputRef = useRef(null);
  const [currentUser, setCurrentUser] = useState(getStoredUser);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout();
      setCurrentUser(null);
    });
  }, []);

  useEffect(() => {
    if (!currentUser) return;
    getHealth().then(setHealth).catch((e) => setError(e.message));
    getRecordStats().then(setStats).catch((e) => setError(e.message));
  }, [refreshTick, currentUser]);

  useEffect(() => {
    if (!currentUser) return;
    listRecords({ source, category, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((data) => {
        setRecords(data.items);
        setTotal(data.total);
      })
      .catch((e) => setError(e.message));
  }, [source, category, page, refreshTick, currentUser]);

  if (!currentUser) {
    return <Login onLoggedIn={(result) => setCurrentUser({ username: result.username, role: result.role })} />;
  }

  const canReview = currentUser.role === "admin";

  function handleLogout() {
    logout();
    setCurrentUser(null);
  }

  async function handleUpload(e) {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    setUploadResult(null);
    try {
      const result = await uploadRecords(file, uploadSource);
      setUploadResult(result);
      fileInputRef.current.value = "";
      setUploadSource("");
      setRefreshTick((t) => t + 1); // pull fresh stats + records so the upload shows up immediately
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleFindCandidates(recordId) {
    setCandidatesLoading(recordId);
    setCandidatesError(null);
    try {
      const result = await getCandidates(recordId, { topK: 8 });
      setCandidatesById((prev) => ({ ...prev, [recordId]: result.candidates }));
    } catch (err) {
      setCandidatesError(err.message);
    } finally {
      setCandidatesLoading(null);
    }
  }

  async function handleEvaluate(recordAId, recordBId) {
    setEvaluationLoading(true);
    setEvaluationError(null);
    setEvaluation(null);
    try {
      const result = await evaluatePair(recordAId, recordBId);
      setEvaluation(result);
    } catch (err) {
      setEvaluationError(err.message);
    } finally {
      setEvaluationLoading(false);
    }
  }

  async function handleViewGroup(recordId) {
    setGroupLoading(recordId);
    try {
      const result = await getRecordGroup(recordId);
      setGroupById((prev) => ({ ...prev, [recordId]: result.group }));
    } catch (err) {
      setError(err.message);
    } finally {
      setGroupLoading(null);
    }
  }

  const activeLabel = NAV_ITEMS.find((n) => n.key === activeTab)?.label || "";

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-brand">SIH26099</div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              className={activeTab === key ? "nav-item active" : "nav-item"}
              onClick={() => setActiveTab(key)}
            >
              <Icon />
              {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <span className="name">{currentUser.username}</span>
            <span className="role">{currentUser.role}</span>
          </div>
          <button className="logout-btn" onClick={handleLogout}>
            <IconLogout /> Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <h1>{activeLabel}</h1>
          <span className={`badge ${health?.mongodb_connected ? "ok" : "down"}`}>
            {health ? (health.mongodb_connected ? "backend + db connected" : "db unreachable") : "connecting..."}
          </span>
        </div>

        {error && <div className="error">{error}</div>}

        {activeTab === "review" && <ReviewQueue canReview={canReview} />}
        {activeTab === "groups" && <MaterialGroups />}
        {activeTab === "dashboard" && <Dashboard />}
        {activeTab === "legacy" && <LegacyMapping />}

        {activeTab === "explorer" && <>

        {stats && (
        <section className="stats">
          <div className="stat-card">
            <div className="stat-value">{stats.total.toLocaleString()}</div>
            <div className="stat-label">total records</div>
          </div>
          {Object.entries(stats.by_source).map(([src, count]) => (
            <div className="stat-card" key={src}>
              <div className="stat-value">{count.toLocaleString()}</div>
              <div className="stat-label">{src}</div>
            </div>
          ))}
        </section>
      )}

      <section className="upload-panel">
        <h2>Upload a material master (Phase 1: ingestion)</h2>
        {canReview ? (
          <form onSubmit={handleUpload} className="upload-form">
            <input type="file" accept=".csv,.xlsx,.xls" ref={fileInputRef} required />
            <input
              type="text"
              placeholder="source label (optional, defaults to filename)"
              value={uploadSource}
              onChange={(e) => setUploadSource(e.target.value)}
            />
            <button type="submit" disabled={uploading}>
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </form>
        ) : (
          <p className="hint">Your role ({currentUser.role}) can view data but not ingest new records. Ask an admin to upload.</p>
        )}
        <p className="hint">
          Accepts .csv/.xlsx with columns for cpse, legacy_code (or material_code), and description
          (or raw_description) — common naming variants are recognized automatically, including SAP's
          own field names (BUKRS/MATNR/MAKTX/WERKS/MEINS — Phase 9 ERP integration). Every row is
          normalized and attribute-extracted immediately on ingest.
        </p>
        {uploadError && <div className="error">{uploadError}</div>}
        {uploadResult && (
          <div className="upload-success">
            Inserted {uploadResult.rows_inserted} rows from "{uploadResult.filename}" (source: {uploadResult.source}).
          </div>
        )}
      </section>

      <section className="filters">
        <label>
          Source:
          <select value={source} onChange={(e) => { setSource(e.target.value); setPage(0); }}>
            <option value="">all</option>
            <option value="samanvay">samanvay</option>
            <option value="custom_gap_test_set">custom_gap_test_set</option>
          </select>
        </label>
        <label>
          Category:
          <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(0); }}>
            <option value="">all</option>
            {stats && Object.keys(stats.by_category).sort().map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
      </section>

      <table className="records-table">
        <thead>
          <tr>
            <th>CPSE</th>
            <th>Legacy Code</th>
            <th>Description</th>
            <th>Category (true / predicted)</th>
            <th>Missing critical</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => {
            const isOpen = expandedId === r._id;
            const categoryMismatch = r.category_true && r.category_predicted !== r.category_true;
            return (
              <Fragment key={r._id}>
                <tr
                  className="clickable-row"
                  onClick={() => setExpandedId(isOpen ? null : r._id)}
                >
                  <td>{r.cpse}</td>
                  <td>{r.legacy_code}</td>
                  <td>{r.description}</td>
                  <td className={categoryMismatch ? "mismatch" : ""}>
                    {r.category_true || "—"} / {r.category_predicted || "unclassified"}
                  </td>
                  <td>
                    {r.missing_critical && r.missing_critical.length > 0 ? (
                      r.missing_critical.map((a) => (
                        <span className="badge-missing" key={a}>{a}</span>
                      ))
                    ) : (
                      <span className="badge-ok">none</span>
                    )}
                  </td>
                  <td>{r.source}</td>
                </tr>
                {isOpen && (
                  <tr className="detail-row">
                    <td colSpan={6}>
                      <div className="detail-panel">
                        <div>
                          <strong>Normalized:</strong> {r.normalized_description}
                        </div>
                        <div className="attr-chips">
                          {r.attributes && Object.keys(r.attributes).length > 0 ? (
                            Object.entries(r.attributes).map(([k, v]) => (
                              <span className={`chip ${v === null ? "chip-empty" : ""}`} key={k}>
                                {k}: {v === null ? "missing" : v}
                              </span>
                            ))
                          ) : (
                            <span className="chip chip-empty">no attributes extracted</span>
                          )}
                        </div>

                        <div className="candidates-section">
                          <button
                            className="find-candidates-btn"
                            onClick={(e) => { e.stopPropagation(); handleFindCandidates(r._id); }}
                            disabled={candidatesLoading === r._id}
                          >
                            {candidatesLoading === r._id ? "Searching..." : "Find similar materials (Phase 3)"}
                          </button>
                          <button
                            className="find-candidates-btn group-btn"
                            onClick={(e) => { e.stopPropagation(); handleViewGroup(r._id); }}
                            disabled={groupLoading === r._id}
                          >
                            {groupLoading === r._id ? "Looking up..." : "View material group (Phase 6)"}
                          </button>
                          {groupById[r._id] !== undefined && (
                            groupById[r._id] === null ? (
                              <p className="hint">Not yet part of any Common Material Group.</p>
                            ) : (
                              <div className="group-trace">
                                <span className="common-code">{groupById[r._id].common_code}</span>
                                <span className="group-desc">{groupById[r._id].canonical_description}</span>
                                <table className="group-members-table">
                                  <thead><tr><th>CPSE</th><th>Original code</th></tr></thead>
                                  <tbody>
                                    {groupById[r._id].members.map((m) => (
                                      <tr key={m.record_id}><td>{m.cpse}</td><td>{m.legacy_code}</td></tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )
                          )}
                          {candidatesError && candidatesLoading === null && (
                            <div className="error">{candidatesError}</div>
                          )}
                          {candidatesById[r._id] && (
                            <>
                            <p className="hint">Click a candidate row to run it through the Phase 4 compatibility engine.</p>
                            <table className="candidates-table">
                              <thead>
                                <tr>
                                  <th>CPSE</th>
                                  <th>Legacy Code</th>
                                  <th>Description</th>
                                  <th>Embedding sim</th>
                                  <th>Attr. agreement</th>
                                  <th>Score</th>
                                </tr>
                              </thead>
                              <tbody>
                                {candidatesById[r._id].length === 0 && (
                                  <tr><td colSpan={6}>No candidates found.</td></tr>
                                )}
                                {candidatesById[r._id].map((c) => (
                                  <tr
                                    key={c.record_id}
                                    className="candidate-row"
                                    onClick={(e) => { e.stopPropagation(); handleEvaluate(r._id, c.record_id); }}
                                  >
                                    <td>{c.cpse}</td>
                                    <td>{c.legacy_code}</td>
                                    <td>{c.description}</td>
                                    <td>{c.embedding_similarity.toFixed(3)}</td>
                                    <td>{c.attribute_agreement.toFixed(2)}</td>
                                    <td className="score-cell">{c.score.toFixed(3)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            </>
                          )}

                          {evaluationLoading && <p className="hint">Evaluating pair...</p>}
                          {evaluationError && <div className="error">{evaluationError}</div>}
                          {evaluation && (
                            <div className={`verdict-panel verdict-${evaluation.verdict}`}>
                              <div className="verdict-header">
                                <span className="verdict-badge">{evaluation.verdict}</span>
                                <span className="verdict-confidence">confidence: {evaluation.confidence}</span>
                                <span className="verdict-confidence">
                                  embedding sim: {evaluation.embedding_similarity?.toFixed(3)}
                                </span>
                              </div>
                              <table className="verdict-attr-table">
                                <thead>
                                  <tr>
                                    <th>Attribute</th>
                                    <th>{evaluation.record_a.legacy_code} ({evaluation.record_a.cpse})</th>
                                    <th>{evaluation.record_b.legacy_code} ({evaluation.record_b.cpse})</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {Object.keys({
                                    ...evaluation.record_a.attributes,
                                    ...evaluation.record_b.attributes,
                                  }).map((attr) => {
                                    const va = evaluation.record_a.attributes[attr];
                                    const vb = evaluation.record_b.attributes[attr];
                                    const isConflict = evaluation.conflicting_attributes.some((c) => c.attribute === attr);
                                    const isMissing = evaluation.missing_attributes.includes(attr);
                                    const rowClass = isConflict ? "attr-conflict" : isMissing ? "attr-missing" : "attr-match";
                                    return (
                                      <tr key={attr} className={rowClass}>
                                        <td>{attr}</td>
                                        <td>{va ?? "—"}</td>
                                        <td>{vb ?? "—"}</td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                              <ul className="verdict-reasons">
                                {evaluation.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>

      <footer className="pagination">
        <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Prev</button>
        <span>Page {page + 1} of {Math.max(1, Math.ceil(total / PAGE_SIZE))} ({total.toLocaleString()} records)</span>
        <button disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage((p) => p + 1)}>Next</button>
      </footer>

      </>}
      </main>
    </div>
  );
}

export default App;
