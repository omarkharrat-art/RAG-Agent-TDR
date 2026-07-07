import { File, ExternalLink } from "./icons.jsx";
import { documentUrl } from "../services/api.js";

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function prettyTitle(filename) {
  return filename
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Build a Google-style snippet: a window of text around the first query match.
function makeSnippet(text, query, len = 320) {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  const terms = query.toLowerCase().split(/\s+/).filter((t) => t.length > 2);
  let start = 0;
  for (const t of terms) {
    const i = clean.toLowerCase().indexOf(t);
    if (i >= 0) {
      start = Math.max(0, i - 70);
      break;
    }
  }
  let s = clean.slice(start, start + len);
  if (start > 0) s = "… " + s;
  if (start + len < clean.length) s = s + " …";
  return s;
}

function Highlighted({ text, query }) {
  const terms = query.toLowerCase().split(/\s+/).filter((t) => t.length > 2);
  if (!terms.length) return <>{text}</>;
  const re = new RegExp(`(${terms.map(escapeRe).join("|")})`, "gi");
  const parts = text.split(re);
  return (
    <>
      {parts.map((p, i) =>
        terms.includes(p.toLowerCase()) ? <mark key={i}>{p}</mark> : <span key={i}>{p}</span>
      )}
    </>
  );
}

export default function ResultCard({ result, query }) {
  const { filename, score, content } = result;
  const pct = Math.round((score || 0) * 100);
  const url = documentUrl(filename);
  const snippet = makeSnippet(content, query);

  return (
    <article className="card gresult">
      <div className="g-url">
        <File size={13} />
        <span>{filename}</span>
      </div>

      <a className="g-title" href={url} target="_blank" rel="noreferrer">
        {prettyTitle(filename)}
      </a>

      <p className="g-snippet">
        <Highlighted text={snippet} query={query} />
      </p>

      <div className="g-foot">
        <div className="g-score">
          <div className="bar">
            <span style={{ width: `${pct}%` }} />
          </div>
          <span className="g-score-label">{pct}% pertinence</span>
        </div>
        <a className="g-open" href={url} target="_blank" rel="noreferrer">
          Ouvrir le document
          <ExternalLink size={14} />
        </a>
      </div>
    </article>
  );
}
