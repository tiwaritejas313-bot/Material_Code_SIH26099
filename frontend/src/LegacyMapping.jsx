import { useState } from "react";
import { legacyMappingSearch } from "./api";
import { IconSearch } from "./Icons";
import { CnmcBanner, SourceTiles } from "./SharedUi";

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
      <div className="dashboard-panel">
        <form onSubmit={handleSearch} className="upload-form">
          <span className="search-field">
            <IconSearch width={16} height={16} />
            <input
              type="text"
              placeholder="Search a common code (CNMC-000001) or an original CPSE code (e.g. B5980)"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              style={{ minWidth: 400 }}
            />
          </span>
          <button type="submit" disabled={loading}>
            {loading ? "Searching..." : "Search"}
          </button>
        </form>
      </div>

      {error && <div className="error">{error}</div>}

      {result && result.match_type === "common_code" && (
        <div className="dashboard-panel">
          <h3 className="card-title">Common Code → all original CPSE codes</h3>
          <p className="hint" style={{ marginTop: 0, marginBottom: 12 }}>
            Matched directly on Common Material Code "{result.query}".
          </p>
          <div className="group-trace" style={{ marginTop: 0 }}>
            <CnmcBanner code={result.group.common_code} />
            <div className="std-desc">
              <div className="std-desc-label">Standardized Description</div>
              {result.group.canonical_description}
            </div>
            <SourceTiles members={result.group.members} />
          </div>
        </div>
      )}

      {result && result.match_type === "legacy_code" && (
        <div className="dashboard-panel">
          <h3 className="card-title">Original code → Common Code</h3>
          <p className="hint" style={{ marginTop: 0, marginBottom: 12 }}>
            Matched an original CPSE record for "{result.query}".
          </p>
          <table className="kv-table">
            <tbody>
              <tr>
                <td>CPSE</td>
                <td>{result.record.cpse}</td>
              </tr>
              <tr>
                <td>Original Code</td>
                <td>{result.record.legacy_code}</td>
              </tr>
              <tr>
                <td>Description</td>
                <td>{result.record.description}</td>
              </tr>
              <tr>
                <td>Category</td>
                <td>{result.record.category_predicted || "unclassified"}</td>
              </tr>
              <tr>
                <td>Common Code</td>
                <td>
                  {result.common_code ? (
                    <span className="common-code">{result.common_code}</span>
                  ) : (
                    "Not yet mapped -- no approved match for this record"
                  )}
                </td>
              </tr>
            </tbody>
          </table>

          {result.group && (
            <>
              <h4>All CPSE codes mapped to {result.group.common_code}</h4>
              <div className="group-trace" style={{ marginTop: 0 }}>
                <CnmcBanner code={result.group.common_code} />
                <div className="std-desc">
                  <div className="std-desc-label">Standardized Description</div>
                  {result.group.canonical_description}
                </div>
                <SourceTiles members={result.group.members} />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
