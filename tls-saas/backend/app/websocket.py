"""
WebSocket Manager
Handles real-time connections for live monitoring updates.
"""

from __future__ import annotations
import json
import asyncio
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections grouped by user and topic."""

    def __init__(self):
        # user_id -> set of WebSocket connections
        self._user_connections: Dict[int, Set[WebSocket]] = {}
        # "admin" connections for admin dashboard
        self._admin_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect_user(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        async with self._lock:
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(websocket)

    async def connect_admin(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._admin_connections.add(websocket)

    async def disconnect_user(self, websocket: WebSocket, user_id: int):
        async with self._lock:
            if user_id in self._user_connections:
                self._user_connections[user_id].discard(websocket)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]

    async def disconnect_admin(self, websocket: WebSocket):
        async with self._lock:
            self._admin_connections.discard(websocket)

    async def send_to_user(self, user_id: int, data: dict):
        """Send a message to all connections of a specific user."""
        connections = self._user_connections.get(user_id, set()).copy()
        dead = []
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        # Clean up dead connections
        for ws in dead:
            await self.disconnect_user(ws, user_id)

    async def send_to_admins(self, data: dict):
        """Broadcast a message to all admin connections."""
        dead = []
        for ws in self._admin_connections.copy():
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect_admin(ws)

    async def broadcast_check_result(self, branch_name: str, service_type: str,
                                      slots_available: bool, slot_details: dict | None,
                                      subscriber_user_ids: list[int]):
        """Notify all subscribers of a branch about a check result."""
        data = {
            "type": "check_result",
            "branch": branch_name,
            "service_type": service_type,
            "slots_available": slots_available,
            "slot_details": slot_details,
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
        for uid in subscriber_user_ids:
            await self.send_to_user(uid, data)
        # Also notify admins
        await self.send_to_admins({**data, "type": "admin_check_result", "subscribers_notified": len(subscriber_user_ids)})

    async def broadcast_admin_event(self, event_type: str, details: dict):
        """Send admin-only event (new payment, new user, etc.)."""
        await self.send_to_admins({"type": event_type, **details})

    @property
    def connected_users_count(self) -> int:
        return len(self._user_connections)

    @property
    def connected_admins_count(self) -> int:
        return len(self._admin_connections)


# Singleton
ws_manager = ConnectionManager()
