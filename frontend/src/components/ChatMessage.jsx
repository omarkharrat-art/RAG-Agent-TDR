import ReflectionBanner from "./ReflectionBanner.jsx";
import SimilarMissions from "./SimilarMissions.jsx";
import LoadingIndicator from "./LoadingIndicator.jsx";

export default function ChatMessage({ message }) {
  if (message.role === "user") {
    return (
      <div className="msg-user">
        <div className="bubble">{message.content}</div>
      </div>
    );
  }

  // assistant
  return (
    <div className="msg-assistant">
      <div className="avatar">EY</div>
      <div className="content">
        {message.pending ? (
          <div className="answer">
            <LoadingIndicator /> &nbsp;Génération de la réponse…
          </div>
        ) : (
          <>
            <ReflectionBanner text={message.reflection} />
            <div className="answer">{message.content}</div>
            <SimilarMissions sources={message.sources} />
          </>
        )}
      </div>
    </div>
  );
}
