import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import { getWebSocketClient, resetWebSocketClient, type WebSocketEventHandler } from '@/api';
import type { WebSocketMessage } from '@/types';
import { useAuth } from './AuthContext';

interface WebSocketContextValue {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  subscribe: (handler: WebSocketEventHandler) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
}

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      resetWebSocketClient();
      setIsConnected(false);
      return;
    }

    const client = getWebSocketClient();

    const unsubscribe = client.subscribe((message) => {
      if (message.type === 'connected') {
        setIsConnected(true);
      } else if (message.type === 'disconnected') {
        setIsConnected(false);
      }
      setLastMessage(message);
    });

    client.connect();

    return () => {
      unsubscribe();
      client.disconnect();
    };
  }, [isAuthenticated]);

  const subscribe = useCallback((handler: WebSocketEventHandler) => {
    const client = getWebSocketClient();
    return client.subscribe(handler);
  }, []);

  return (
    <WebSocketContext.Provider value={{ isConnected, lastMessage, subscribe }}>
      {children}
    </WebSocketContext.Provider>
  );
}
