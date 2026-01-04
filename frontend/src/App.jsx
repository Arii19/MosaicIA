import { useEffect, useMemo, useState } from 'react';
import ChatWindow from './components/ChatWindow.jsx';
import Sidebar from './components/Sidebar.jsx';
import { useChat } from './hooks/useChat.js';
import './App.css';

const DEFAULT_USER_ID = 'ariane';
const STORAGE_KEY = 'mosaic.apiBaseUrl';

const normalizeBaseUrl = (raw) => {
  const sanitized = (raw || '').trim();
  if (!sanitized) {
    return '';
  }
  return sanitized.endsWith('/') ? sanitized.slice(0, -1) : sanitized;
};

function App() {
  const [userId, setUserId] = useState(DEFAULT_USER_ID);
  const [prefill, setPrefill] = useState('');

  const defaultApiBase = useMemo(() => normalizeBaseUrl(import.meta.env.VITE_API_URL ?? '/api'), []);

  const [apiBaseUrl, setApiBaseUrl] = useState(() => {
    if (typeof window === 'undefined') {
      return defaultApiBase;
    }

    const stored = window.localStorage.getItem(STORAGE_KEY);
    return normalizeBaseUrl(stored) || defaultApiBase;
  });

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, apiBaseUrl || defaultApiBase);
  }, [apiBaseUrl, defaultApiBase]);

  const handleApiBaseChange = (nextBase) => {
    const normalized = normalizeBaseUrl(nextBase);
    setApiBaseUrl(normalized || defaultApiBase);
  };

  const {
    chatPairs,
    messages,
    isLoading,
    isSending,
    error,
    sendMessage,
    resetChat,
    refresh,
    showHistory,
  } = useChat(apiBaseUrl, userId);

  const handleReset = async () => {
    await resetChat();
    setPrefill('');
  };

  return (
    <div className="app-shell">
      <Sidebar
        userId={userId}
        onUserIdChange={setUserId}
        apiBaseUrl={apiBaseUrl}
        onApiBaseChange={handleApiBaseChange}
        chatPairs={chatPairs}
        onReset={handleReset}
        onRefresh={refresh}
        isLoading={isLoading}
        onPrefill={setPrefill}
        onShowHistory={showHistory}
      />
      <ChatWindow
        userId={userId}
        messages={messages}
        isLoading={isLoading}
        isSending={isSending}
        error={error}
        onSend={sendMessage}
        onReset={handleReset}
        canSend={Boolean((userId || '').trim())}
        prefill={prefill}
        clearPrefill={() => setPrefill('')}
      />
    </div>
  );
}

export default App;
