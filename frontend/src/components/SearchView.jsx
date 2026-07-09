import { useState, useEffect } from "react";
import SearchBar from "./SearchBar.jsx";
import FilterPanel from "./FilterPanel.jsx";
import ResultsList from "./ResultsList.jsx";
import LoadingIndicator from "./LoadingIndicator.jsx";
import { search } from "../services/api.js";

const HISTORY_KEY = "tdr_search_history";
const MAX_HISTORY = 30;

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
  } catch {
    return [];
  }
}

export default function SearchView({ docCount }) {
  const [results, setResults] = useState(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeFilters, setActiveFilters] = useState([]);
  const [history, setHistory] = useState(loadHistory);
  const [showHistory, setShowHistory] = useState(false);

  // Persist history whenever it changes.
  useEffect(() => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  }, [history]);

  const runSearch = async (q) => {
    setQuery(q);
    setLoading(true);
    setError("");
    try {
      const data = await search(q, 10);
      const items = data.results || [];
      setResults(items);
      // Record this search (dedupe, most-recent first, keep a full snapshot so
      // reopening a history entry restores its results instantly).
      setHistory((h) => {
        const rest = h.filter((e) => e.query !== q);
        return [
          { query: q, count: items.length, at: Date.now(), results: items },
          ...rest,
        ].slice(0, MAX_HISTORY);
      });
    } catch (e) {
      setError(e.message || "La recherche a échoué.");
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  // Reopen a past search from history: restore its query + results without a
  // new network call.
  const openHistory = (entry) => {
    setQuery(entry.query);
    setResults(entry.results || []);
    setError("");
  };

  const removeHistory = (q) =>
    setHistory((h) => h.filter((e) => e.query !== q));
  const clearHistory = () => setHistory([]);

  const toggleFilter = (key) =>
    setActiveFilters((f) =>
      f.includes(key) ? f.filter((x) => x !== key) : [...f, key]
    );

  return (
    <div className={`search-layout ${showHistory ? "with-history" : ""}`}>
      {/* History side panel — slides in and pushes the results over. */}
      <aside className="history-panel" aria-hidden={!showHistory}>
        <div className="history-head">
          <span>Historique</span>
          {history.length > 0 && (
            <button className="history-clear" onClick={clearHistory}>
              Tout effacer
            </button>
          )}
        </div>
        {history.length === 0 ? (
          <p className="history-empty">Aucune recherche pour l'instant.</p>
        ) : (
          <ul className="history-list">
            {history.map((e) => (
              <li key={e.query + e.at} className="history-item">
                <button
                  className="history-q"
                  onClick={() => openHistory(e)}
                  title={e.query}
                >
                  <span className="history-q-text">{e.query}</span>
                  <span className="history-q-meta">{e.count} résultats</span>
                </button>
                <button
                  className="history-del"
                  onClick={() => removeHistory(e.query)}
                  aria-label="Supprimer"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <main className="search-view">
        <div className="hero-band">
        <div className="hero">
          <div className="hero-top">
            <button
              className={`history-toggle ${showHistory ? "on" : ""}`}
              onClick={() => setShowHistory((v) => !v)}
              title="Afficher l'historique"
            >
              🕘 Historique{history.length ? ` (${history.length})` : ""}
            </button>
          </div>
          <h1>
            Trouvez le bon <span className="accent">Terme de Référence</span>
          </h1>
          <p>
            Recherche sémantique sur {docCount != null ? docCount : "les"} TdR
            indexés — profils, compétences et missions similaires.
          </p>
        </div>

        <SearchBar onSearch={runSearch} loading={loading} />
        <FilterPanel active={activeFilters} onToggle={toggleFilter} />
        </div>

        {error && <div className="banner">{error}</div>}

        {loading && (
          <div className="empty-state">
            <LoadingIndicator /> &nbsp;Recherche en cours…
          </div>
        )}

        {!loading && results && results.length > 0 && (
          <ResultsList results={results} query={query} />
        )}

        {!loading && results && results.length === 0 && (
          <div className="empty-state">
            Aucun résultat pour « {query} ». Essayez d'autres termes.
          </div>
        )}

        {!loading && !results && !error && (
          <div className="empty-state">
            Lancez une recherche pour explorer les {docCount != null ? docCount : ""} TdR
            indexés.
          </div>
        )}
      </main>
    </div>
  );
}
