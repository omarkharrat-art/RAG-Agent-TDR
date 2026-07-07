import { Sun, Moon } from "./icons.jsx";
import LogoEY from "./LogoEY.jsx";

export default function Header({ tab, onTab, theme, onToggleTheme, docCount }) {
  return (
    <header className="header">
      <div className="brand">
        <LogoEY height={38} />
        <span className="app-name">TdR&nbsp;Explorer</span>
        {docCount != null && (
          <span className="corpus-badge">{docCount} TdR</span>
        )}
      </div>
      <nav className="nav">
        <button
          className={"tab" + (tab === "search" ? " active" : "")}
          onClick={() => onTab("search")}
        >
          Recherche
        </button>
        <button
          className={"tab" + (tab === "assistant" ? " active" : "")}
          onClick={() => onTab("assistant")}
        >
          Assistant
        </button>
        <button
          className="toggle"
          onClick={onToggleTheme}
          aria-label="Changer de thème"
          title={theme === "dark" ? "Mode clair" : "Mode sombre"}
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
      </nav>
    </header>
  );
}
