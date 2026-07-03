import { Briefcase, Calendar, Bank, MapPin, World, ChevronDown } from "./icons.jsx";

// Filter chips. The corpus doesn't yet carry structured metadata
// (domaine / bailleur / pays / région / dates live in phase6 metadata,
// still to be extracted), so these are presentational toggles for now.
// Once metadata is indexed, wire each chip to a dropdown + query param.
const FILTERS = [
  { key: "domaine", label: "Domaine", Icon: Briefcase },
  { key: "dates", label: "Dates", Icon: Calendar },
  { key: "bailleur", label: "Bailleur", Icon: Bank },
  { key: "pays", label: "Pays", Icon: MapPin },
  { key: "region", label: "Région", Icon: World },
];

export default function FilterPanel({ active, onToggle }) {
  return (
    <div className="filters">
      {FILTERS.map(({ key, label, Icon }) => (
        <button
          key={key}
          className={"chip" + (active.includes(key) ? " active" : "")}
          onClick={() => onToggle(key)}
        >
          <Icon size={14} />
          {label}
          <ChevronDown size={13} />
        </button>
      ))}
    </div>
  );
}
