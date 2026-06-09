"""Intent classifier — scores message complexity to pick the right model tier.

Uses fast heuristics (no API call) to decide:
- "fast" tier: greetings, short casual chat, simple acknowledgments
- "smart" tier: questions needing reasoning, multi-step requests, technical topics
"""

from __future__ import annotations

import re

# Patterns that signal a simple/casual message
_CASUAL_PATTERNS = [
    r"^(hey|hi|hello|yo|sup|what'?s? ?up|gm|gn|good morning|good night)\b",
    r"^(thanks|thank you|ty|thx|ok|okay|k|cool|nice|lol|lmao|haha|bet|word)\b",
    r"^(yes|no|yep|nope|nah|yeah|yea|sure)\b",
]

# Patterns that signal a complex/reasoning message
_COMPLEX_PATTERNS = [
    r"\b(explain|how does|how do|why does|why do|what is|what are|who is|who are)\b",
    r"\b(compare|difference between|pros and cons|analyze|evaluate)\b",
    r"\b(write me|draft|create|generate|build|implement|code|script)\b",
    r"\b(step by step|in detail|elaborate|break down)\b",
    r"\b(calculate|solve|convert|translate)\b",
    r"\b(summarize|tldr|recap)\b",
    r"\b(research|find out|look up|search for)\b",
    r"\?.*\?",  # multiple questions
]

# Word count thresholds
_SHORT_MSG_THRESHOLD = 5
_LONG_MSG_THRESHOLD = 30


def classify(text: str) -> str:
    """Return 'fast' or 'smart' based on message complexity.

    The classifier uses a simple scoring system:
    - Starts at 0
    - Casual patterns subtract points
    - Complex patterns add points
    - Message length influences the score
    - Score <= 0 → "fast", score > 0 → "smart"
    """
    text_lower = text.lower().strip()
    words = text_lower.split()
    word_count = len(words)
    score = 0

    # Very short messages are almost always casual
    if word_count <= _SHORT_MSG_THRESHOLD:
        score -= 2

    # Long messages tend to be more complex
    if word_count >= _LONG_MSG_THRESHOLD:
        score += 2

    # Check casual patterns
    for pattern in _CASUAL_PATTERNS:
        if re.search(pattern, text_lower):
            score -= 3
            break

    # Check complex patterns
    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, text_lower):
            score += 3
            break

    # Questions (single ?) get a small bump
    if "?" in text and score == 0:
        score += 1

    return "smart" if score > 0 else "fast"
