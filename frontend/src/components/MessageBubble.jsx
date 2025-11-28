function MessageBubble({ message }) {
  if (!message) {
    return null;
  }

  const roleClass = message.role === 'user' ? 'message-bubble--user' : 'message-bubble--assistant';
  const avatar = message.role === 'user' ? '🧑' : '🤖';
  const label = message.role === 'user' ? 'Você' : 'Mosaic';
  const timestamp = message.createdAt
    ? new Date(message.createdAt).toLocaleTimeString('pt-BR', {
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';
  const lines = (message.content || '').split('\n');

  return (
    <article className={`message-bubble ${roleClass}`}>
      <div className="message-bubble__avatar" aria-hidden>
        {avatar}
      </div>
      <div className="message-bubble__body">
        <span className="message-bubble__meta">
          {label}
          {timestamp ? ` · ${timestamp}` : ''}
        </span>
        <div className="message-bubble__content">
          {lines.map((line, index) => (
            <span key={`${message.id}-line-${index}`}>
              {line === '' ? '\u00a0' : line}
              {index < lines.length - 1 ? <br /> : null}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}

export default MessageBubble;
