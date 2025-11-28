import { useMemo, useState } from 'react';
import ChatWindow from './components/ChatWindow.jsx';
import Sidebar from './components/Sidebar.jsx';
import { useChat } from './hooks/useChat.js';
import './App.css';

const DEFAULT_USER_ID = 'ariane';

function App() {
  const [userId, setUserId] = useState(DEFAULT_USER_ID);
  const [prefill, setPrefill] = useState('');

  const apiBaseUrl = useMemo(() => {
    const raw = import.meta.env.VITE_API_URL ?? '/api';
    return raw.endsWith('/') ? raw.slice(0, -1) : raw;
  }, []);

  const {
    chatPairs,
    messages,
    isLoading,
    isSending,
    error,
    sendMessage,
    resetChat,
    refresh,
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
        chatPairs={chatPairs}
        onReset={handleReset}
        onRefresh={refresh}
        isLoading={isLoading}
        onPrefill={setPrefill}
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
