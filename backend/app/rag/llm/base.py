from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a completion for the given prompt and system instructions."""
        pass

    @abstractmethod
    def generate_chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Generate a response given a list of chat message dictionaries."""
        pass
