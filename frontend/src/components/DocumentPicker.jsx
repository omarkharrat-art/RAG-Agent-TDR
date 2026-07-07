import { useEffect, useState } from "react";
import { listDocuments } from "../services/api.js";
import { File } from "./icons.jsx";

// Dropdown to scope questions to a single TdR. "Tous les documents" (value "")
// means no filter — search the whole corpus.
export default function DocumentPicker({ value, onChange }) {
  const [docs, setDocs] = useState([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    listDocuments()
      .then((d) => alive && setDocs(d.documents || []))
      .catch(() => alive && setError(true));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="docpicker" title="Limiter la recherche à un document">
      <File size={14} />
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={error}
      >
        <option value="">Tous les documents</option>
        {docs.map((d) => (
          <option key={d.filename} value={d.filename}>
            {d.filename}
          </option>
        ))}
      </select>
    </div>
  );
}
