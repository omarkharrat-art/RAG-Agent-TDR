import { useEffect, useRef, useState } from "react";
import HistorySidebar from "./HistorySidebar.jsx";
import ChatMessage from "./ChatMessage.jsx";
import DocumentPicker from "./DocumentPicker.jsx";
import { ArrowUp } from "./icons.jsx";
import LogoEY from "./LogoEY.jsx";
import {
  listConversations,
  createConversation,
  getConversation,
  deleteConversation,
  sendMessage,
} from "../services/api.js";

const SUGGESTIONS = [
  "Quels profils pour une évaluation genre en Afrique de l'Ouest ?",
  "Quels sont les livrables attendus d'une mission d'audit ?",
  "Quelles compétences pour un consultant en pêche durable ?",
];

export default function AssistantView() {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [selectedDoc, setSelectedDoc] = useState(null);

  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  const refreshList = async () => {
    try {
      setConversations(await listConversations());
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    refreshList();
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const selectConversation = async (id) => {
    setError("");
    setActiveId(id);
    try {
      const conv = await getConversation(id);
      setMessages(conv.messages || []);
    } catch (e) {
      setError(e.message);
    }
  };

  const newConversation = () => {
    setActiveId(null);
    setMessages([]);
    setError("");
    textareaRef.current?.focus();
  };

  const removeConversation = async (id) => {
    try {
      await deleteConversation(id);
      if (id === activeId) newConversation();
      refreshList();
    } catch (e) {
      setError(e.message);
    }
  };

  const submit = async (text) => {
    const query = (text ?? input).trim();
    if (!query || sending) return;

    setInput("");
    setError("");
    setSending(true);

    // Optimistic UI: show the user's message and a pending assistant bubble.
    setMessages((m) => [
      ...m,
      { role: "user", content: query, id: `tmp-u-${Date.now()}` },
      { role: "assistant", pending: true, id: `tmp-a-${Date.now()}` },
    ]);

    try {
      let convId = activeId;
      if (!convId) {
        const conv = await createConversation();
        convId = conv.id;
        setActiveId(convId);
      }

      const res = await sendMessage(convId, query, { document: selectedDoc });

      setMessages((m) => {
        const kept = m.filter((x) => !x.pending);
        return [...kept, res.assistant_message];
      });
      refreshList();
    } catch (e) {
      setError(e.message || "L'envoi a échoué.");
      // Drop the pending bubble on failure.
      setMessages((m) => m.filter((x) => !x.pending));
    } finally {
      setSending(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="assistant">
      <HistorySidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNew={newConversation}
        onDelete={removeConversation}
      />

      <section className="chat">
        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-inner">
            {isEmpty ? (
              <div className="chat-empty">
                <LogoEY height={58} letter="var(--tx)" />
                <h2>Assistant TdR</h2>
                <p>
                  Posez une question en français ou en anglais. Les réponses
                  sont générées à partir des TdR indexés, avec les sources
                  citées.
                </p>
                <div className="suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => submit(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => <ChatMessage key={m.id} message={m} />)
            )}
            {error && <div className="banner">{error}</div>}
          </div>
        </div>

        <div className="composer">
          <div className="composer-tools">
            <DocumentPicker value={selectedDoc} onChange={setSelectedDoc} />
          </div>
          <div className="box">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Posez une question sur les TdR…"
            />
            <button
              className="send"
              onClick={() => submit()}
              disabled={sending || !input.trim()}
              aria-label="Envoyer"
            >
              <ArrowUp size={18} />
            </button>
          </div>
          <div className="hint">
            Les réponses sont générées à partir des TdR indexés — vérifiez les
            sources citées.
          </div>
        </div>
      </section>
    </div>
  );
}
