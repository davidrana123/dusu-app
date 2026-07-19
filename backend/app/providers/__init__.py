"""Wiring point: pick the concrete provider here. Swap a line to change vendor."""

from .openrouter_provider import OpenRouterLLM

llm = OpenRouterLLM()

__all__ = ["llm"]
