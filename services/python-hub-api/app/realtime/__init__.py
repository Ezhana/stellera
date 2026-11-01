"""FDE 订单实时推送。

浏览器 WebSocket 无法设置 Authorization 头，令牌校验放在端点里（见
app/api/v1/endpoints/fde.py）；本模块只维护连接集合并广播 JSON 消息。
"""

from app.realtime.hub import RealtimeHub

__all__ = ["RealtimeHub"]
