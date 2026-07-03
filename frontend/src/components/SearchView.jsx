import { useState } from "react";
import SearchBar from "./SearchBar.jsx";
import FilterPanel from "./FilterPanel.jsx";
import ResultsList from "./ResultsList.jsx";
import LoadingIndicator from "./LoadingIndicator.jsx";
import { search } from "../services/api.js";

export default function SearchView() {
  const [results, setResults] = useState(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeFilters, setActiveFilters] = useState([]);

  const runSearch = async (q) => {
    setQuery(q);
    setLoading(true);
    setError("");
    try {
      const data = await search(q, 10);
      setResults(data.results || []);
    } catch (e) {
      setError(e.message || "La recherche a échoué.");
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const toggleFilter = (key) =>
    setActiveFilters((f) =>
      f.includes(key) ? f.filter((x) => x !== key) : [...f, key]
    );

  return (
    <main className="search-view">
      <div className="hero">
        <h1>
          Trouvez le bon <span className="accent">Terme de Référence</span>
        </h1>
        <p>
          Recherche sémantique sur les TdR indexés — profils, compétences et
          missions similaires.
        </p>
      </div>

      <SearchBar onSearch={runSearch} loading={loading} />
      <FilterPanel active={activeFilters} onToggle={toggleFilter} />

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
          Lancez une recherche pour explorer les 100 TdR indexés.
        </div>
      )}
    </main>
  );
}
