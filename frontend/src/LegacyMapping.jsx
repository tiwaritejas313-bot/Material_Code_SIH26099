import { useState } from "react";
import { legacyMappingSearch } from "./api";

export default function LegacyMapping() {
  const [code, setCode] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSearch(e) {
    e.preventDefault();
    if (!code.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await legacyMappingSearch(code.trim());
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="legacy-mapping">
      <div className="review-toolbar">
        <form onSubmit={handleSearch} className="upload-form">
          <input
            type="text"
            placeholder="Search a common code (CNMC-000001) or an original CPSE code (e.g. B5980)"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            style={{ minWidth: 360 }}
          />
          <button type="submit" disabled={loading}>{loading ? "Searching..." : "Search"}</button>
        </form>
      </div>

      {error && <div className="error">{error}</div>}

      {result && result.match_type === "common_code" && (
        <div className="dashboard-panel">
          <h3>Common Code → all original CPSE codes</h3>
          <p className="hint">Matched directly on Common Material Code "{result.query}".</p>
          <span className="common-code">{result.group.common_code}</span>
          <span className="group-desc"> {result.group.canonical_description}</span>
          <table className="group-members-table">
            <thead><tr><th>CPSE</th><th>Original code</th></tr></thead>
            <tbody>
              {result.group.members.map((m) => (
                <tr key={m.record_id}><td>{m.cpse}</td><td>{m.legacy_code}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result && result.match_type === "legacy_code" && (
        <div className="dashboard-panel">
          <h3>Original code → Common Code</h3>
          <p className="hint">Matched an original CPSE record for "{result.query}".</p>
          <table className="group-members-table">
            <tbody>
              <tr><td>CPSE</td><td>{result.record.cpse}</td></tr>
              <tr><td>Original Code</td><td>{result.record.legacy_code}</td></tr>
              <tr><td>Description</td><td>{result.record.description}</td></tr>
              <tr><td>Category</td><td>{result.record.category_predicted || "unclassified"}</td></tr>
              <tr>
                <td>Common Code</td>
                <td>{result.common_code ? <span className="common-code">{result.common_code}</span> : "Not yet mapped -- no approved match for this record"}</td>
              </tr>
            </tbody>
          </table>

          {result.group && (
            <>
              <h4>All CPSE codes mapped to {result.group.common_code}</h4>
              <table className="group-members-table">
                <thead><tr><th>CPSE</th><th>Original code</th></tr></thead>
                <tbody>
                  {result.group.members.map((m) => (
                    <tr key={m.record_id}><td>{m.cpse}</td><td>{m.legacy_code}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}
