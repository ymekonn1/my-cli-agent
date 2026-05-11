"""
skills/__init__.py

Exposes the @skill decorator and get_skill_registry() at the package level,
so all existing imports (`from skills import get_skill_registry`) work unchanged.

Built-in skills are defined in skills/builtins.py. Importing this package
automatically triggers their registration via the import at the bottom.
"""

_SKILL_REGISTRY: dict[str, callable] = {}


def skill(fn):
    """Decorator that registers a function as a named skill."""
    _SKILL_REGISTRY[fn.__name__] = fn
    return fn


def get_skill_registry() -> dict[str, callable]:
    """Returns the global skill registry (name → callable)."""
    return _SKILL_REGISTRY


# Import builtins last to trigger @skill registration
from skills import builtins  # noqa: E402, F401
