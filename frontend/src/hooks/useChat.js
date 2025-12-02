import { useCallback, useEffect, useMemo, useState } from 'react';

export function useChat(apiBaseUrl, userId) {
  const [chatPairs, setChatPairs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
  const [sessionAnchor, setSessionAnchor] = useState(() => Date.now());

  const baseUrl = useMemo(() => {
    const sanitized = (apiBaseUrl || '/api').trim() || '/api';
    return sanitized.endsWith('/') ? sanitized.slice(0, -1) : sanitized;
  }, [apiBaseUrl]);

  const fetchHistory = useCallback(async () => {
    const trimmedUser = (userId || '').trim();

    if (!trimmedUser) {
      setChatPairs([]);
      setError('');
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${baseUrl}/history/${encodeURIComponent(trimmedUser)}`);
      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(payload?.detail || 'Falha ao carregar o histórico.');
      }

      setChatPairs(Array.isArray(payload) ? payload : []);
      setError('');
    } catch (historyError) {
      setError(historyError.message || 'Falha ao carregar o histórico.');
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl, userId]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  useEffect(() => {
    setSessionAnchor(Date.now());
  }, [userId]);

  const messages = useMemo(() => {
    if (!Array.isArray(chatPairs) || chatPairs.length === 0) {
      return [];
    }

    const orderedPairs = [...chatPairs].sort((a, b) => {
      const aDate = new Date(a.created_at || 0).getTime();
      const bDate = new Date(b.created_at || 0).getTime();
      return aDate - bDate;
    });

    return orderedPairs
      .filter((pair) => {
        const createdAt = new Date(pair.created_at || 0).getTime();
        if (Number.isNaN(createdAt)) {
          return true;
        }
        return createdAt >= sessionAnchor;
      })
      .flatMap((pair) => {
      const items = [];
      if (pair.question) {
        items.push({
          id: `${pair.id}-question`,
          role: 'user',
          content: pair.question,
          createdAt: pair.created_at,
        });
      }

      if (pair.answer) {
        items.push({
          id: `${pair.id}-answer`,
          role: 'assistant',
          content: pair.answer,
          createdAt: pair.created_at,
          sources: pair.sources,
        });
      }

      return items;
    });
  }, [chatPairs, sessionAnchor]);

  const sendMessage = useCallback(
    async (question) => {
      const trimmedUser = (userId || '').trim();
      const trimmedQuestion = (question || '').trim();

      if (!trimmedUser || !trimmedQuestion) {
        const reason = !trimmedUser
          ? 'Defina um usuário para enviar mensagens.'
          : 'Digite uma pergunta antes de enviar.';
        setError(reason);
        return;
      }

      const tempId = `temp-${Date.now()}`;
      const now = new Date().toISOString();
      const pendingRecord = {
        id: tempId,
        user_id: trimmedUser,
        question: trimmedQuestion,
        answer: '',
        created_at: now,
        sources: [],
      };

      setChatPairs((previous) => [...previous, pendingRecord]);
      setIsSending(true);

      try {
        const response = await fetch(`${baseUrl}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ user_id: trimmedUser, question: trimmedQuestion }),
        });

        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(payload.detail || 'Falha ao enviar a mensagem.');
        }

        setChatPairs((previous) =>
          previous.map((record) => (record.id === tempId ? payload : record)),
        );
        setError('');
      } catch (sendError) {
        setChatPairs((previous) => previous.filter((record) => record.id !== tempId));
        setError(sendError.message || 'Falha ao enviar a mensagem.');
        throw sendError;
      } finally {
        setIsSending(false);
      }
    },
    [baseUrl, userId],
  );

  const resetChat = useCallback(async () => {
    const trimmedUser = (userId || '').trim();

    const latestTimestamp = Array.isArray(chatPairs)
      ? chatPairs.reduce((latest, pair) => {
          const createdAt = new Date(pair?.created_at || 0).getTime();
          if (!Number.isFinite(createdAt)) {
            return latest;
          }
          return Math.max(latest, createdAt);
        }, Date.now())
      : Date.now();

    setSessionAnchor(Math.max(Date.now(), latestTimestamp + 1));

    if (!trimmedUser) {
      setError('');
      setChatPairs([]);
      return;
    }

    try {
      await fetch(`${baseUrl}/reset/${encodeURIComponent(trimmedUser)}`, {
        method: 'POST',
      });
    } catch (resetError) {
      if (import.meta.env.DEV) {
        console.warn('Erro ao resetar a conversa:', resetError);
      }
    }

    await fetchHistory();
    setError('');
  }, [baseUrl, userId, chatPairs, fetchHistory]);

  const showHistory = useCallback((createdAt) => {
    if (!createdAt) {
      setSessionAnchor(0);
      return;
    }

    const timestamp = new Date(createdAt).getTime();
    if (Number.isNaN(timestamp)) {
      setSessionAnchor(0);
      return;
    }

    setSessionAnchor(timestamp - 1);
  }, []);

  return {
    chatPairs,
    messages,
    isLoading,
    isSending,
    error,
    sendMessage,
    resetChat,
    refresh: fetchHistory,
    showHistory,
  };
}
