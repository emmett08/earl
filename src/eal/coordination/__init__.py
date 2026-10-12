"""Single-host, durable coordination of registered EAL tasks through MCP."""

from .contracts import ServerSpec, TaskSpec

__all__ = ["Coordinator", "ServerSpec", "TaskSpec"]


def __getattr__(name):
    if name == "Coordinator":
        from .service import Coordinator
        return Coordinator
    raise AttributeError(name)
