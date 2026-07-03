import { useEffect, useState } from "react";
import Header from "./components/Header.jsx";
import SearchView from "./components/SearchView.jsx";
import AssistantView from "./components/AssistantView.jsx";

export default function App() {
  const [tab, setTab] = useState("search");
  const [theme, setTheme] = useState(
    () => localStorage.getItem("ey-theme") || "dark"
  );

  // Apply the theme to <html> so the CSS variables switch, and remember it.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("ey-theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return (
    <div className="app">
      <Header
        tab={tab}
        onTab={setTab}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
      {tab === "search" ? <SearchView /> : <AssistantView />}
    </div>
  );
}
