import { useEffect, useMemo, useState } from 'react';

function formatDate(value) {
  if (!value) {
    return 'Sem data';
  }

  try {
    return new Date(value).toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (error) {
    return 'Sem data';
  }
}

function Sidebar({
  userId,
  onUserIdChange,
  chatPairs,
  onReset,
  onRefresh,
  isLoading,
  onPrefill,
  onShowHistory,
}) {
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return window.innerWidth <= 820;
  });

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const handleResize = () => {
      if (window.innerWidth > 820) {
        setCollapsed(false);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const orderedHistory = useMemo(() => {
    if (!chatPairs || chatPairs.length === 0) {
      return [];
    }
    return [...chatPairs].sort((a, b) => {
      const aDate = new Date(a.created_at || 0).getTime();
      const bDate = new Date(b.created_at || 0).getTime();
      return bDate - aDate;
    });
  }, [chatPairs]);

  const handleToggle = () => {
    setCollapsed((prev) => !prev);
  };

  const handleSelectHistory = (item) => {
    if (onShowHistory) {
      onShowHistory(item?.created_at);
    }

    if (onPrefill) {
      onPrefill(item?.question);
    }

    if (typeof window !== 'undefined' && window.innerWidth <= 820) {
      setCollapsed(true);
    }
  };

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''}`}>
      <div className="sidebar__header">
        <div className="sidebar__brand">
          <img src="/mosaic_20251124_232058.png" alt="Mosaic IA" className="sidebar__logo" />
          <img
            src="/605e2afebb3af870a9d35b2f_smartbreederWhiteLogo.png"
            alt="SmartBreeder"
            className="sidebar__logo sidebar__logo--secondary"
          />
        </div>
        <button type="button" className="sidebar__toggle" onClick={handleToggle}>
          {collapsed ? 'Mostrar menu' : 'Ocultar menu'}
        </button>
      </div>

      <div className="sidebar__content">
        <div className="sidebar__input-wrapper">
          <label className="sidebar__label" htmlFor="sidebar-user-id">
            ID do usuário
          </label>
          <input
            id="sidebar-user-id"
            className="sidebar__input"
            placeholder="Ex.: ariane"
            value={userId}
            onChange={(event) => onUserIdChange?.(event.target.value)}
          />
        </div>

        <div className="sidebar__actions">
          <button
            type="button"
            className="sidebar__button sidebar__button--primary"
            onClick={onReset}
            disabled={!userId?.trim() || isLoading}
          >
            Novo chat
          </button>
          <button
            type="button"
            className="sidebar__button sidebar__button--ghost"
            onClick={onRefresh}
            disabled={isLoading}
          >
            Atualizar histórico
          </button>
        </div>

        <div className="sidebar__history">
          {isLoading ? (
            <div className="sidebar__history-item" aria-hidden>
              Carregando histórico...
            </div>
          ) : null}

          {!isLoading && orderedHistory.length === 0 ? (
            <div className="sidebar__history-empty">Nenhuma conversa registrada ainda.</div>
          ) : null}

          {orderedHistory.map((item) => (
            <button
              type="button"
              key={item.id}
              className="sidebar__history-item"
              onClick={() => handleSelectHistory(item)}
            >
              <span className="sidebar__history-question">{item.question}</span>
              <span className="sidebar__history-date">{formatDate(item.created_at)}</span>
            </button>
          ))}
        </div>

        <div className="sidebar__footer">
          <span className="sidebar__badge">RAG</span>
          <span className="sidebar__badge">Gemini 2.5</span>
          <span className="sidebar__badge">FastAPI</span>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
