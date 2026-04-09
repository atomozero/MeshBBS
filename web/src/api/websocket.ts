/**
 * WebSocket client for real-time updates.
 */

import type { WebSocketMessage } from '@/types';
import { getAccessToken } from './client';

export type WebSocketEventHandler = (message: WebSocketMessage) => void;

export interface WebSocketClient {
  connect: () => void;
  disconnect: () => void;
  isConnected: () => boolean;
  subscribe: (handler: WebSocketEventHandler) => () => void;
}

/**
 * Create a WebSocket client for real-time updates.
 */
export function createWebSocketClient(url?: string): WebSocketClient {
  let socket: WebSocket | null = null;
  let reconnectAttempts = 0;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  const handlers = new Set<WebSocketEventHandler>();
  const maxReconnectAttempts = 5;
  const baseReconnectDelay = 1000;

  const getWebSocketUrl = (): string => {
    if (url) return url;

    const token = getAccessToken();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    return token ? `${wsUrl}?token=${encodeURIComponent(token)}` : wsUrl;
  };

  const notifyHandlers = (message: WebSocketMessage) => {
    handlers.forEach((handler) => {
      try {
        handler(message);
      } catch (error) {
        console.error('WebSocket handler error:', error);
      }
    });
  };

  const scheduleReconnect = () => {
    if (reconnectAttempts >= maxReconnectAttempts) {
      console.error('Max WebSocket reconnection attempts reached');
      notifyHandlers({
        type: 'connection_error',
        data: { message: 'Connection lost. Please refresh the page.' },
        timestamp: new Date().toISOString(),
      });
      return;
    }

    const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts);
    reconnectAttempts++;

    console.log(`Scheduling WebSocket reconnect in ${delay}ms (attempt ${reconnectAttempts})`);

    reconnectTimeout = setTimeout(() => {
      connect();
    }, delay);
  };

  const connect = () => {
    if (socket?.readyState === WebSocket.OPEN) {
      return;
    }

    // Clear any existing socket
    if (socket) {
      socket.onclose = null;
      socket.onerror = null;
      socket.onmessage = null;
      socket.close();
    }

    try {
      const wsUrl = getWebSocketUrl();
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.log('WebSocket connected');
        reconnectAttempts = 0;
        notifyHandlers({
          type: 'connected',
          data: {},
          timestamp: new Date().toISOString(),
        });
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          notifyHandlers(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      socket.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        notifyHandlers({
          type: 'disconnected',
          data: { code: event.code, reason: event.reason },
          timestamp: new Date().toISOString(),
        });

        // Only reconnect if it wasn't a clean close
        if (event.code !== 1000) {
          scheduleReconnect();
        }
      };

      socket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      scheduleReconnect();
    }
  };

  const disconnect = () => {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }

    reconnectAttempts = maxReconnectAttempts; // Prevent reconnection

    if (socket) {
      socket.onclose = null;
      socket.close(1000, 'Client disconnecting');
      socket = null;
    }
  };

  const isConnected = (): boolean => {
    return socket?.readyState === WebSocket.OPEN;
  };

  const subscribe = (handler: WebSocketEventHandler): (() => void) => {
    handlers.add(handler);
    return () => {
      handlers.delete(handler);
    };
  };

  return {
    connect,
    disconnect,
    isConnected,
    subscribe,
  };
}

// Default singleton instance
let defaultClient: WebSocketClient | null = null;

export function getWebSocketClient(): WebSocketClient {
  if (!defaultClient) {
    defaultClient = createWebSocketClient();
  }
  return defaultClient;
}

export function resetWebSocketClient(): void {
  if (defaultClient) {
    defaultClient.disconnect();
    defaultClient = null;
  }
}
