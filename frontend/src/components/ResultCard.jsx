import { File, Calendar } from "./icons.jsx";

// Turn a raw filename into a more readable title.
function prettyTitle(filename) {
  return filename
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export default function ResultCard({ result }) {
  const { filename, chunk_index, score, snippet } = result;
  const weak = score < 0.85;

  return (
    <article className="card">
      <div className="row">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 className="title">{prettyTitle(filename)}</h3>
          <div className="meta">
            <span>
              <File size={13} />
              {filename}
            </span>
            <span>
              <Calendar size={13} />
              extrait #{chunk_index}
            </span>
          </div>
          {snippet && <p className="snippet">{snippet}</p>}
        </div>
        <div className="score">
          <div className={"val" + (weak ? " weak" : "")}>{score.toFixed(2)}</div>
          <div className="lbl">score</div>
        </div>
      </div>
    </article>
  );
}
