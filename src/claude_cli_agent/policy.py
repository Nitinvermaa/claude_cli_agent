"""Safety and approval policy checks."""

from __future__ import annotations

import re

MUTATION_PATTERNS = [
    r"\bimplement\b",
    r"\bbuild\b",
    r"\bcreate\b",
    r"\bmodify\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\brefactor\b",
    r"\bfix\b",
    r"\bwrite\b",
    r"\bscaffold\b",
]

PUSH_PATTERNS = [
    r"\bpush\b",
    r"\bdeploy\b",
    r"\brelease\b",
    r"\bpublish\b",
]

COMMIT_PATTERNS = [
    r"\bcommit\b",
    r"\bgit commit\b",
    r"\bcheck in\b",
]


def needs_change_confirmation(prompt: str) -> bool:
    text = prompt.lower()
    return any(re.search(pat, text) for pat in MUTATION_PATTERNS)


def needs_push_confirmation(prompt: str) -> bool:
    text = prompt.lower()
    return any(re.search(pat, text) for pat in PUSH_PATTERNS)


def needs_commit_confirmation(prompt: str) -> bool:
    text = prompt.lower()
    return any(re.search(pat, text) for pat in COMMIT_PATTERNS)
