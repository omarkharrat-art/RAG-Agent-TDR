import { Sparkles } from "./icons.jsx";

// Small yellow banner that surfaces the agentic step (query reformulation +
// how many TdR were consulted) attached to an assistant reply.
export default function ReflectionBanner({ text }) {
  if (!text) return null;
  return (
    <div className="reflection">
      <Sparkles size={14} />
      <span>{text}</span>
    </div>
  );
}
