import { Fragment, useEffect, useRef, useState } from "react";
import {
  evaluatePair,
  getCandidates,
  getHealth,
  getRecordGroup,
  getRecordStats,
  getStoredUser,
  listRecords,
  logout,
  setUnauthorizedHandler,
  uploadRecords,
} from "./api";
import Dashboard from "./Dashboard";
import {
  IconChart,
  IconChecklist,
  IconCheck,
  IconGrid,
  IconLink,
  IconLogout,
  IconSearch,
  IconUpload,
} from "./Icons";
import LegacyMapping from "./LegacyMapping";
import Login from "./Login";
import MaterialGroups from "./MaterialGroups";
import ReviewQueue from "./ReviewQueue";
import { CnmcBanner, MatchVerdict, PageHead, SourceTiles } from "./SharedUi";
import "./App.css";

const NAV_ITEMS = [
  {
    key: "explorer",
    label: "Material Explorer",
    icon: IconGrid,
    subtitle:
      "Ingest CPSE material masters, find similar materials and verify matches",
  },
  {
    key: "review",
    label: "Review Queue",
    icon: IconChecklist,
    subtitle:
      "Accept, reject or escalate the matches the system is unsure about",
  },
  {
    key: "groups",
    label: "Material Groups",
    icon: IconLink,
    subtitle: "Approved common codes and every CPSE code mapped to them",
  },
  {
    key: "dashboard",
    label: "Dashboard",
    icon: IconChart,
    subtitle:
      "Live view of what needs attention, what is processed and data quality",
  },
  {
    key: "legacy",
    label: "Legacy Mapping",
    icon: IconSearch,
    subtitle: "Look up a common code or an original CPSE code",
  },
];

// The SAP-style columns the ingestion pipeline recognises, with the plain-name
// variants it also accepts. Used only to PREVIEW detection for CSV files in
// the browser; the server still does the real column mapping on upload.
const COLUMN_MAP = [
  {
    key: "MATNR",
    label: "Material Number",
    aliases: ["MATNR", "LEGACY_CODE", "MATERIAL_CODE"],
  },
  {
    key: "MAKTX",
    label: "Short Description",
    aliases: ["MAKTX", "DESCRIPTION", "RAW_DESCRIPTION"],
  },
  { key: "BUKRS", label: "Company Code", aliases: ["BUKRS", "CPSE"] },
  { key: "WERKS", label: "Plant", aliases: ["WERKS", "PLANT"] },
  { key: "MEINS", label: "Base Unit of Measure", aliases: ["MEINS", "UOM"] },
];

function parseCsvHeader(text) {
  const firstLine = (text || "").split(/\r?\n/)[0] || "";
  return firstLine
    .split(/[,;\t]/)
    .map((c) =>
      c
        .replace(/^\uFEFF/, "")
        .replace(/^["']|["']$/g, "")
        .trim()
        .toUpperCase(),
    )
    .filter(Boolean);
}

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
  const [selectedFile, setSelectedFile] = useState(null);
  const [headerCols, setHeaderCols] = useState(null);
  const [dragOver, setDragOver] = useState(false);
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
    getHealth()
      .then(setHealth)
      .catch((e) => setError(e.message));
    getRecordStats()
      .then(setStats)
      .catch((e) => setError(e.message));
  }, [refreshTick, currentUser]);

  useEffect(() => {
    if (!currentUser) return;
    listRecords({
      source,
      category,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    })
      .then((data) => {
        setRecords(data.items);
        setTotal(data.total);
      })
      .catch((e) => setError(e.message));
  }, [source, category, page, refreshTick, currentUser]);

  if (!currentUser) {
    return (
      <Login
        onLoggedIn={(result) =>
          setCurrentUser({ username: result.username, role: result.role })
        }
      />
    );
  }

  const canReview = currentUser.role === "admin";

  function handleLogout() {
    logout();
    setCurrentUser(null);
  }

  // Remember the chosen file (from the picker or a drop) and, for CSV, read
  // just the header row so the "Detected Columns" panel can show a preview.
  async function selectFile(file) {
    setSelectedFile(file || null);
    setHeaderCols(null);
    setUploadResult(null);
    setUploadError(null);
    if (file && /\.csv$/i.test(file.name)) {
      try {
        const text = await file.slice(0, 8192).text();
        setHeaderCols(parseCsvHeader(text));
      } catch {
        setHeaderCols(null);
      }
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer?.files;
    if (files && files.length > 0 && fileInputRef.current) {
      fileInputRef.current.files = files;
      selectFile(files[0]);
    }
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
      setSelectedFile(null);
      setHeaderCols(null);
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

  const activeIndex = Math.max(
    0,
    NAV_ITEMS.findIndex((n) => n.key === activeTab),
  );
  const activeItem = NAV_ITEMS[activeIndex];

  const isXlsx = selectedFile && /\.xlsx?$/i.test(selectedFile.name);
  const columnNote = !selectedFile
    ? "Choose a file to preview which columns are detected."
    : headerCols
      ? "Preview read from the CSV header row. The server does the final column mapping on upload."
      : isXlsx
        ? "Excel columns are mapped by the server when you upload."
        : "Columns are mapped by the server when you upload.";

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark">S</div>
          <div>
            <div className="brand-name"></div>
            <div className="brand-sub">Material Harmonization</div>
          </div>
        </div>
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
          <PageHead
            num={String(activeIndex + 1).padStart(2, "0")}
            title={activeItem.label}
            subtitle={activeItem.subtitle}
            right={
              <span
                className={`badge ${health?.mongodb_connected ? "ok" : "down"}`}
              >
                {health
                  ? health.mongodb_connected
                    ? "backend + db connected"
                    : "db unreachable"
                  : "connecting..."}
              </span>
            }
          />
        </div>

        {error && <div className="error">{error}</div>}

        {activeTab === "review" && <ReviewQueue canReview={canReview} />}
        {activeTab === "groups" && <MaterialGroups />}
        {activeTab === "dashboard" && <Dashboard />}
        {activeTab === "legacy" && <LegacyMapping />}

        {activeTab === "explorer" && (
          <>
            {stats && (
              <section className="stats">
                <div className="stat-card">
                  <div className="stat-value">
                    {stats.total.toLocaleString()}
                  </div>
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
              <h2 className="card-title">
                <span className="card-num">1.</span> Data Ingestion
                <span className="card-sub">
                  Upload a material master (Phase 1)
                </span>
              </h2>
              {canReview ? (
                <form onSubmit={handleUpload} className="ingest-grid">
                  <div className="ingest-col">
                    <div className="upload-label">Upload Material Data</div>
                    <div
                      className={`dropzone${dragOver ? " dragover" : ""}${selectedFile ? " has-file" : ""}`}
                      onDragOver={(e) => {
                        e.preventDefault();
                        setDragOver(true);
                      }}
                      onDragLeave={() => setDragOver(false)}
                      onDrop={handleDrop}
                    >
                      {selectedFile ? <IconCheck /> : <IconUpload />}
                      {selectedFile ? (
                        <div className="dz-file">{selectedFile.name}</div>
                      ) : (
                        <>
                          <div className="dz-title">
                            Drag &amp; drop your file here
                          </div>
                          <div className="dz-or">or</div>
                        </>
                      )}
                      <label className="choose-btn">
                        {selectedFile
                          ? "Choose a different file"
                          : "Choose File"}
                        <input
                          type="file"
                          accept=".csv,.xlsx,.xls"
                          ref={fileInputRef}
                          hidden
                          onChange={(e) => selectFile(e.target.files?.[0])}
                        />
                      </label>
                      <div className="dz-support">
                        Supports CSV, Excel (XLSX) and SAP export files
                      </div>
                    </div>
                    <input
                      type="text"
                      className="source-input"
                      placeholder="source label (optional, defaults to filename)"
                      value={uploadSource}
                      onChange={(e) => setUploadSource(e.target.value)}
                    />
                  </div>

                  <div className="ingest-col">
                    <div className="upload-label">Detected Columns</div>
                    <div className="col-panel">
                      <ul className="col-list">
                        {COLUMN_MAP.map((col) => {
                          const detected = headerCols
                            ? col.aliases.some((a) => headerCols.includes(a))
                            : null;
                          const state =
                            detected === true
                              ? "on"
                              : detected === false
                                ? "off"
                                : "idle";
                          return (
                            <li key={col.key} className={`col-item ${state}`}>
                              <span className="col-check">
                                {detected === true && (
                                  <IconCheck
                                    width={12}
                                    height={12}
                                    strokeWidth={3.2}
                                  />
                                )}
                              </span>
                              <span className="col-name">{col.key}</span>
                              <span className="col-desc">{col.label}</span>
                            </li>
                          );
                        })}
                      </ul>
                      <p className="col-note">{columnNote}</p>
                    </div>
                    <button
                      type="submit"
                      className="btn-success"
                      disabled={uploading || !selectedFile}
                    >
                      {uploading ? "Uploading..." : "Map & Continue"}
                    </button>
                  </div>
                </form>
              ) : (
                <p className="hint">
                  Your role ({currentUser.role}) can view data but not ingest
                  new records. Ask an admin to upload.
                </p>
              )}
              <p className="hint">
                Accepts .csv/.xlsx with columns for cpse, legacy_code (or
                material_code), and description (or raw_description) — common
                naming variants are recognized automatically, including SAP's
                own field names (BUKRS/MATNR/MAKTX/WERKS/MEINS — Phase 9 ERP
                integration). Every row is normalized and attribute-extracted
                immediately on ingest.
              </p>
              {uploadError && (
                <div className="error" style={{ marginTop: 12 }}>
                  {uploadError}
                </div>
              )}
              {uploadResult && (
                <div className="upload-success">
                  Inserted {uploadResult.rows_inserted} rows from "
                  {uploadResult.filename}" (source: {uploadResult.source}).
                </div>
              )}
            </section>

            <section className="filters">
              <label>
                Source:
                <select
                  value={source}
                  onChange={(e) => {
                    setSource(e.target.value);
                    setPage(0);
                  }}
                >
                  <option value="">all</option>
                  <option value="samanvay">samanvay</option>
                  <option value="custom_gap_test_set">
                    custom_gap_test_set
                  </option>
                </select>
              </label>
              <label>
                Category:
                <select
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value);
                    setPage(0);
                  }}
                >
                  <option value="">all</option>
                  {stats &&
                    Object.keys(stats.by_category)
                      .sort()
                      .map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                </select>
              </label>
            </section>

            <div className="table-wrap">
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
                    const categoryMismatch =
                      r.category_true &&
                      r.category_predicted !== r.category_true;
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
                            {r.category_true || "—"} /{" "}
                            {r.category_predicted || "unclassified"}
                          </td>
                          <td>
                            {r.missing_critical &&
                            r.missing_critical.length > 0 ? (
                              r.missing_critical.map((a) => (
                                <span className="badge-missing" key={a}>
                                  {a}
                                </span>
                              ))
                            ) : (
                              <span className="badge-ok">none</span>
                            )}
                          </td>
                          <td>
                            <span className="source-chip">{r.source}</span>
                          </td>
                        </tr>
                        {isOpen && (
                          <tr className="detail-row">
                            <td colSpan={6}>
                              <div className="detail-panel">
                                <div>
                                  <div className="detail-normalized">
                                    <strong>Normalized:</strong>{" "}
                                    {r.normalized_description}
                                  </div>
                                  <div className="attr-chips">
                                    {r.attributes &&
                                    Object.keys(r.attributes).length > 0 ? (
                                      Object.entries(r.attributes).map(
                                        ([k, v]) => (
                                          <span
                                            className={`chip ${v === null ? "chip-empty" : ""}`}
                                            key={k}
                                          >
                                            {k}: {v === null ? "missing" : v}
                                          </span>
                                        ),
                                      )
                                    ) : (
                                      <span className="chip chip-empty">
                                        no attributes extracted
                                      </span>
                                    )}
                                  </div>
                                </div>

                                <div className="detail-section candidates-section">
                                  <h3 className="card-title">
                                    <span className="card-num">2.</span>{" "}
                                    Matching &amp; Verification
                                  </h3>
                                  <div className="btn-row">
                                    <button
                                      className="find-candidates-btn"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleFindCandidates(r._id);
                                      }}
                                      disabled={candidatesLoading === r._id}
                                    >
                                      {candidatesLoading === r._id
                                        ? "Searching..."
                                        : "Find similar materials (Phase 3)"}
                                    </button>
                                  </div>
                                  {candidatesError &&
                                    candidatesLoading === null && (
                                      <div
                                        className="error"
                                        style={{ marginTop: 12 }}
                                      >
                                        {candidatesError}
                                      </div>
                                    )}
                                  {candidatesById[r._id] && (
                                    <>
                                      <p className="hint">
                                        Click a candidate row to run it through
                                        the Phase 4 compatibility engine.
                                      </p>
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
                                          {candidatesById[r._id].length ===
                                            0 && (
                                            <tr>
                                              <td colSpan={6}>
                                                No candidates found.
                                              </td>
                                            </tr>
                                          )}
                                          {candidatesById[r._id].map((c) => (
                                            <tr
                                              key={c.record_id}
                                              className="candidate-row"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                handleEvaluate(
                                                  r._id,
                                                  c.record_id,
                                                );
                                              }}
                                            >
                                              <td>{c.cpse}</td>
                                              <td>{c.legacy_code}</td>
                                              <td>{c.description}</td>
                                              <td>
                                                {c.embedding_similarity.toFixed(
                                                  3,
                                                )}
                                              </td>
                                              <td>
                                                {c.attribute_agreement.toFixed(
                                                  2,
                                                )}
                                              </td>
                                              <td className="score-cell">
                                                {c.score.toFixed(3)}
                                              </td>
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </>
                                  )}

                                  {evaluationLoading && (
                                    <p className="hint">Evaluating pair...</p>
                                  )}
                                  {evaluationError && (
                                    <div
                                      className="error"
                                      style={{ marginTop: 12 }}
                                    >
                                      {evaluationError}
                                    </div>
                                  )}
                                  {evaluation && (
                                    <MatchVerdict
                                      recordA={evaluation.record_a}
                                      recordB={evaluation.record_b}
                                      verdict={evaluation.verdict}
                                      confidence={evaluation.confidence}
                                      similarity={
                                        evaluation.embedding_similarity
                                      }
                                      conflicting={
                                        evaluation.conflicting_attributes
                                      }
                                      missing={evaluation.missing_attributes}
                                      reasons={evaluation.reasons}
                                    />
                                  )}
                                </div>

                                <div className="detail-section">
                                  <h3 className="card-title">
                                    <span className="card-num">3.</span>{" "}
                                    Generated CNMC
                                  </h3>
                                  <div className="btn-row">
                                    <button
                                      className="find-candidates-btn group-btn"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleViewGroup(r._id);
                                      }}
                                      disabled={groupLoading === r._id}
                                    >
                                      {groupLoading === r._id
                                        ? "Looking up..."
                                        : "View material group (Phase 6)"}
                                    </button>
                                  </div>
                                  {groupById[r._id] !== undefined &&
                                    (groupById[r._id] === null ? (
                                      <p className="hint">
                                        Not yet part of any Common Material
                                        Group.
                                      </p>
                                    ) : (
                                      <div className="group-trace">
                                        <CnmcBanner
                                          code={groupById[r._id].common_code}
                                        />
                                        <div className="std-desc">
                                          <div className="std-desc-label">
                                            Standardized Description
                                          </div>
                                          {
                                            groupById[r._id]
                                              .canonical_description
                                          }
                                        </div>
                                        <SourceTiles
                                          members={groupById[r._id].members}
                                        />
                                      </div>
                                    ))}
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
            </div>

            <footer className="pagination">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Prev
              </button>
              <span>
                Page {page + 1} of {Math.max(1, Math.ceil(total / PAGE_SIZE))} (
                {total.toLocaleString()} records)
              </span>
              <button
                disabled={(page + 1) * PAGE_SIZE >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
