"""Request-scoped context shared by logs and audit records."""
from contextvars import ContextVar

request_id_ctx: ContextVar[str | None] = ContextVar('request_id', default=None)
ip_address_ctx: ContextVar[str | None] = ContextVar('ip_address', default=None)
user_agent_ctx: ContextVar[str | None] = ContextVar('user_agent', default=None)
