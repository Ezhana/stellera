"""订单实时推送连接中心。

单进程内存实现（v0.1 不引入 Redis）：订阅方是订单大厅页面，连上后持续接收
`order.created` / `order.updated` 事件。多 worker 部署时每个 worker 只推自己
连接上的客户端，前端仍可通过重新拉取列表兜底。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class RealtimeHub:
    """维护在线 WebSocket 连接，并向所有连接广播消息。"""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        # 增删连接与广播串行化：同一个 WebSocket 并发 send 会被底层拒绝，
        # 广播期间持锁可以保证消息按顺序完整写出，也避免移除连接时读集合。
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """向所有在线连接推送一条 JSON 消息；发送失败的连接直接移除。"""
        payload = json.dumps(message, ensure_ascii=False)
        async with self._lock:
            stale: list[WebSocket] = []
            for websocket in list(self._connections):
                try:
                    await websocket.send_text(payload)
                except Exception:  # 连接可能已断开，移除即可，不能影响其他订阅方。
                    stale.append(websocket)
            for websocket in stale:
                self._connections.discard(websocket)

    async def close_all(self) -> None:
        """关闭全部连接（lifespan 退出时调用）。"""
        async with self._lock:
            connections = list(self._connections)
            self._connections.clear()
            for websocket in connections:
                try:
                    await websocket.close(code=1001)
                except Exception:  # 已经断开的连接忽略即可。
                    pass


__all__ = ["RealtimeHub"]
