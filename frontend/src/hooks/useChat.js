import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

export function useChat(apiBaseUrl, userId) {
  const [chatPairs, setChatPairs] = useState([]);
  const [sessionPairs, setSessionPairs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
  const sessionOverrideRef = useRef(false);

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

      const normalized = Array.isArray(payload) ? payload : [];
      setChatPairs(normalized);
      setSessionPairs((previous) => {
        if (sessionOverrideRef.current) {
          return previous;
        }
        return normalized;
      });
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
    sessionOverrideRef.current = false;
    setSessionPairs([]);
  }, [userId]);

  const parseTimestamp = useCallback((value) => {
    if (!value) {
      return Number.NaN;
    }

    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      return value.getTime();
    }

    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? Number.NaN : parsed;
  }, []);

  const messages = useMemo(() => {
    if (!Array.isArray(sessionPairs) || sessionPairs.length === 0) {
      return [];
    }

    const orderedPairs = [...sessionPairs].sort((a, b) => {
      const aDate = parseTimestamp(a.created_at);
      const bDate = parseTimestamp(b.created_at);
      const safeADate = Number.isNaN(aDate) ? 0 : aDate;
      const safeBDate = Number.isNaN(bDate) ? 0 : bDate;
      return safeADate - safeBDate;
    });

    return orderedPairs.flatMap((pair) => {
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
  }, [parseTimestamp, sessionPairs]);

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

      sessionOverrideRef.current = true;

      setChatPairs((previous) => [...previous, pendingRecord]);
      setSessionPairs((previous) => [...previous, pendingRecord]);
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

        setChatPairs((previous) => previous.map((record) => (record.id === tempId ? payload : record)));
        setSessionPairs((previous) => previous.map((record) => (record.id === tempId ? payload : record)));
        setError('');
      } catch (sendError) {
        setChatPairs((previous) => previous.filter((record) => record.id !== tempId));
        setSessionPairs((previous) => previous.filter((record) => record.id !== tempId));
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

    sessionOverrideRef.current = true;
    if (!trimmedUser) {
      setError('');
      setChatPairs([]);
      setSessionPairs([]);
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

    setSessionPairs([]);
    await fetchHistory();
    setError('');
  }, [baseUrl, userId, fetchHistory]);

  const showHistory = useCallback((createdAt) => {
    sessionOverrideRef.current = true;

    if (!createdAt) {
      setSessionPairs(chatPairs);
      return;
    }

    const timestamp = parseTimestamp(createdAt);
    if (Number.isNaN(timestamp)) {
      setSessionPairs(chatPairs);
      return;
    }

    const filtered = chatPairs.filter((pair) => {
      const createdAtValue = parseTimestamp(pair.created_at);
      if (Number.isNaN(createdAtValue)) {
        return false;
      }
      return createdAtValue >= timestamp;
    });

    setSessionPairs(filtered);
  }, [chatPairs, parseTimestamp]);

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
