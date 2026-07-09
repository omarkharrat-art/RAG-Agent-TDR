import { Plus, Message, Trash } from "./icons.jsx";

// Group conversations into simple date buckets based on updated_at.
function groupByDate(conversations) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const weekAgo = new Date(startOfToday);
  weekAgo.setDate(weekAgo.getDate() - 7);

  const groups = { "Aujourd'hui": [], "Cette semaine": [], "Plus ancien": [] };
  for (const c of conversations) {
    const d = new Date(c.updated_at);
    if (d >= startOfToday) groups["Aujourd'hui"].push(c);
    else if (d >= weekAgo) groups["Cette semaine"].push(c);
    else groups["Plus ancien"].push(c);
  }
  return groups;
}

export default function HistorySidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
}) {
  const groups = groupByDate(conversations);

  return (
    <aside className="sidebar">
      <button className="btn-new" onClick={onNew}>
        <Plus size={15} />
        Nouvelle conversation
      </button>

      <div className="sidebar-list">
        {conversations.length === 0 && (
          <div className="sidebar-empty">Aucune conversation pour l'instant.</div>
        )}

        {Object.entries(groups).map(([label, items]) =>
          items.length === 0 ? null : (
            <div key={label}>
              <div className="hgroup-label">{label}</div>
              {items.map((c) => (
                <button
                  key={c.id}
                  className={"hitem" + (c.id === activeId ? " active" : "")}
                  onClick={() => onSelect(c.id)}
                >
                  <Message size={14} />
                  <span className="htitle">{c.title}</span>
                  <span
                    className="del"
                    role="button"
                    aria-label="Supprimer"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(c.id);
                    }}
                  >
                    <Trash size={14} />
                  </span>
                </button>
              ))}
            </div>
          )
        )}
      </div>
    </aside>
  );
}
