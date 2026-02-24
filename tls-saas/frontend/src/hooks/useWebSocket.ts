"use client";

/**
 * WebSocket hook for real-time updates
 */

import { useEffect, useRef, useState, useCallback } from "react";
import Cookies from "js-cookie";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

interface WSMessage {
  type: string;
  [key: string]: any;
}

export function useWebSocket(isAdmin: boolean = false) {
  const path = isAdmin ? "/api/admin/ws" : "/ws/user";
  const ws = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout>();
  const pingInterval = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    const token = Cookies.get("access_token");
    if (!token) return;

    try {
      ws.current = new WebSocket(`${WS_URL}${path}?token=${token}`);

      ws.current.onopen = () => {
        setConnected(true);
        // Send ping every 30s to keep alive
        pingInterval.current = setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send("ping");
          }
        }, 30000);
      };

      ws.current.onmessage = (event) => {
        if (event.data === "pong") return;
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
        } catch {}
      };

      ws.current.onclose = () => {
        setConnected(false);
        clearInterval(pingInterval.current);
        // Reconnect after 5s
        reconnectTimeout.current = setTimeout(connect, 5000);
      };

      ws.current.onerror = () => {
        ws.current?.close();
      };
    } catch {}
  }, [path]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      clearInterval(pingInterval.current);
      ws.current?.close();
    };
  }, [connect]);

  return { connected, lastMessage };
}
