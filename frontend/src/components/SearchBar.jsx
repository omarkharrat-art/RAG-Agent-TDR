import { useState } from "react";
import { Search } from "./icons.jsx";

export default function SearchBar({ onSearch, loading }) {
  const [value, setValue] = useState("");

  const submit = (e) => {
    e.preventDefault();
    const q = value.trim();
    if (q && !loading) onSearch(q);
  };

  return (
    <form className="searchbar" onSubmit={submit}>
      <div className="field">
        <Search size={18} />
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="expert évaluation genre, Afrique de l'Ouest…"
        />
      </div>
      <button className="btn-primary" type="submit" disabled={loading}>
        <Search size={16} />
        Rechercher
      </button>
    </form>
  );
}
