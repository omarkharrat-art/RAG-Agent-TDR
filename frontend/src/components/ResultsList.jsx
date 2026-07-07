import ResultCard from "./ResultCard.jsx";

export default function ResultsList({ results, query }) {
  return (
    <>
      <div className="results-head">
        <span>
          <b>{results.length}</b> résultat{results.length > 1 ? "s" : ""}
          {query ? ` pour « ${query} »` : ""}
        </span>
        <span>Trié par pertinence</span>
      </div>
      <div className="results">
        {results.map((r, i) => (
          <ResultCard
            key={`${r.filename}-${r.chunk_index}-${i}`}
            result={r}
            query={query}
          />
        ))}
      </div>
    </>
  );
}
