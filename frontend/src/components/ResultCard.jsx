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

// Tidy raw OCR text for display. Ingestion stores scanned pages with '|'
// column markers and occasional OCR noise; that's fine for the LLM but ugly in
// the search view, so we clean it here (display only — the stored data is
// untouched).
function cleanOcr(text) {
  return (text || "")
    // Drop the OCR column separators and page markers.
    .replace(/\|/g, " ")
    .replace(/-{2,}\s*Page\s*\d+\s*-{2,}/gi, " ")
    .replace(/(^|\s)Page\s*\d+(\s|$)/gi, " ")
    // Remove lone stray symbols/letters left by OCR (e.g. "§", solitary "e |").
    .replace(/(^|\s)[^\w\s.,;:()«»'’-]{1,2}(?=\s|$)/g, " ")
    // Collapse runs of single characters separated by spaces ("a S ely claw").
    .replace(/\b(?:[a-zA-Z]\s){3,}[a-zA-Z]\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// A snippet window is "readable" if a decent share of its words are real
// (length >= 3). Garbage OCR windows are mostly 1-2 char tokens.
function readableRatio(s) {
  const words = s.split(/\s+/).filter(Boolean);
  if (!words.length) return 0;
  const real = words.filter((w) => w.length >= 3).length;
  return real / words.length;
}

// Build a Google-style snippet: a window of text around the first query match,
// preferring a readable window over an OCR-garbled one.
function makeSnippet(text, query, len = 320) {
  const clean = cleanOcr(text);
  const terms = query.toLowerCase().split(/\s+/).filter((t) => t.length > 2);

  // Candidate start positions: around each query match, plus the beginning.
  const starts = [];
  for (const t of terms) {
    const i = clean.toLowerCase().indexOf(t);
    if (i >= 0) starts.push(Math.max(0, i - 70));
  }
  starts.push(0);

  // Pick the first candidate whose window reads cleanly; fall back to the
  // first candidate if none clear the bar.
  let start = starts[0];
  for (const cand of starts) {
    if (readableRatio(clean.slice(cand, cand + len)) >= 0.6) {
      start = cand;
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
