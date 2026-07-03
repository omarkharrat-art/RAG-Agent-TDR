import { File } from "./icons.jsx";

// Renders the cited source documents for an assistant reply as compact
// chips (filename + relevance score). Doubles as the "missions similaires"
// surface — the documents the answer was grounded in.
export default function SimilarMissions({ sources }) {
  if (!sources || sources.length === 0) return null;
  return (
    <>
      <div className="sources-label">Sources</div>
      <div className="sources">
        {sources.map((s, i) => (
          <span className="src" key={`${s.filename}-${i}`} title={s.filename}>
            <File size={13} />
            <span className="fn">{s.filename}</span>
            {typeof s.score === "number" && (
              <span className="sc">{s.score.toFixed(2)}</span>
            )}
          </span>
        ))}
      </div>
    </>
  );
}
