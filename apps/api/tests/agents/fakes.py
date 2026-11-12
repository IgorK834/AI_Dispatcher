"""Recording, scripted chat models; constructed only by test registries."""

from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from pydantic import Field


class ScriptedModel(BaseChatModel):
    script: list[Exception | AIMessage]
    recorded: list[list[BaseMessage]] = Field(default_factory=list)
    bindings: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable[Any, Any]:
        self.bindings.append({"tools": tools, **kwargs})
        return self

    def get_num_tokens_from_messages(
        self, messages: list[BaseMessage], tools: Sequence[Any] | None = None
    ) -> int:
        return 20

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.recorded.append(messages)
        response = self.script.pop(0)
        if isinstance(response, Exception):
            raise response
        return ChatResult(generations=[ChatGeneration(message=response)])


def response(
    content: str = "", *, tool: str | None = None, args: dict[str, Any] | None = None
) -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=[{"id": "call", "name": tool, "args": args or {}}] if tool else [],
        usage_metadata={"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
    )
