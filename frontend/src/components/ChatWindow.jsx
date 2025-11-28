import { useEffect, useMemo, useRef, useState } from 'react';
import MessageBubble from './MessageBubble.jsx';

function ChatWindow({
  userId,
  messages,
  isLoading,
  isSending,
  error,
  onSend,
  onReset,
  canSend,
  prefill,
  clearPrefill,
}) {
  const [draft, setDraft] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    if (prefill) {
      setDraft(prefill);
      clearPrefill?.();
    }
  }, [prefill, clearPrefill]);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const placeholder = useMemo(() => {
    if (!canSend) {
      return 'Defina um identificador de usuário para iniciar uma nova conversa.';
    }
    return 'Digite sua mensagem aqui (Shift + Enter para quebrar linha).';
  }, [canSend]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const text = draft.trim();

    if (!text || !canSend) {
      return;
    }

    try {
      await onSend(text);
      setDraft('');
    } catch (sendError) {
      // A mensagem de erro já é exibida pela prop `error`
    }
  };

  const hasMessages = messages && messages.length > 0;
  const disableSend = !draft.trim() || !canSend || isSending;

  return (
    <section className="chat-window">
      <header className="chat-window__header">
        <div>
          <h1 className="chat-window__title">Mosaic Assistant</h1>
          <p className="chat-window__subtitle">
            Seu copiloto especializado em inteligência agrícola com memória por usuário e respostas contextuais.
          </p>
        </div>
        <div className="chat-window__header-actions">
          <button
            type="button"
            className="chat-window__reset"
            onClick={onReset}
            disabled={!canSend || isLoading || isSending}
          >
            Nova conversa
          </button>
        </div>
      </header>

      <div className="chat-window__messages">
        {hasMessages
          ? messages.map((message) => <MessageBubble key={message.id} message={message} />)
          : !isLoading && (
              <div className="chat-window__empty">
                <div className="chat-window__empty-content">
                  <strong>Comece uma nova conversa</strong>
                  <span>Faça uma pergunta para explorar a documentação e histórico treinado do Mosaic.</span>
                </div>
              </div>
            )}
        <span aria-hidden ref={bottomRef} />
      </div>

      <div className="chat-window__composer">
        <form className="chat-window__form" onSubmit={handleSubmit}>
          <textarea
            className="chat-window__textarea"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={placeholder}
            disabled={!canSend}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                handleSubmit(event);
              }
            }}
          />

          <button type="submit" className="chat-window__send" disabled={disableSend}>
            {isSending ? 'Enviando...' : 'Enviar'}
          </button>
        </form>

        {error ? <div className="chat-window__error">{error}</div> : null}
      </div>
    </section>
  );
}

export default ChatWindow;
