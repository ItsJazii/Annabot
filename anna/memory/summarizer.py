"""Conversation summarizer — condenses old messages into rolling summaries.

When a conversation exceeds SUMMARY_TRIGGER messages, the summarizer:
1. Takes the existing summary (if any) + older messages
2. Asks the AI to produce an updated summary
3. Stores the summary and trims old messages locally

The summary captures: key facts about the user, topics discussed,
preferences, writing style, and anything Anna should remember.
"""

from __future__ import annotations

from anna.core.config import logger

SUMMARIZE_PROMPT = """You are a memory system for a personal AI assistant named Anna.

Your job is to read a conversation and produce a concise summary that captures everything Anna needs to remember about this user and their conversations.

Include:
- User's name, location, interests, job, habits (anything personal they've shared)
- Key topics discussed and outcomes
- User's preferences (communication style, things they like/dislike)
- Important requests or tasks the user has mentioned
- Any facts the user asked Anna to remember
- The user's texting style and vibe

Do NOT include:
- Generic filler
- Exact message quotes (paraphrase instead)
- Any internal system details

Format as a natural, dense paragraph. Keep it under 500 words. If there's an existing summary, merge the new information into it (don't lose old facts).
"""


def summarize_conversation(
    ai_provider,
    existing_summary: str,
    messages: list[dict],
) -> str | None:
    """Generate a summary of the conversation so far.

    Uses the fast tier to keep costs at zero (Groq/Cerebras).
    Returns the summary text or None on failure.
    """
    if not messages:
        return existing_summary or None

    # Build the conversation text for the summarizer
    conversation_lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        conversation_lines.append(f"{role}: {content}")

    conversation_text = "\n".join(conversation_lines)

    # Build the prompt
    user_content = ""
    if existing_summary:
        user_content += f"EXISTING SUMMARY (merge new info into this):\n{existing_summary}\n\n"
    user_content += f"NEW CONVERSATION MESSAGES:\n{conversation_text}\n\n"
    user_content += "Produce an updated summary:"

    summary_messages = [{"role": "user", "content": user_content}]

    result = ai_provider.chat(
        messages=summary_messages,
        system_prompt=SUMMARIZE_PROMPT,
        max_tokens=800,
        tier="fast",
    )

    if result:
        logger.info(f"Conversation summarized ({len(messages)} messages → {len(result)} chars)")
    else:
        logger.warning("Summarization failed, keeping existing summary")

    return result or existing_summary or None


def extract_user_facts(
    ai_provider,
    messages: list[dict],
) -> dict[str, str]:
    """Extract key facts about the user from recent messages.

    Returns a dict of fact_key → fact_value pairs.
    Uses the fast tier to keep costs at zero.
    """
    if not messages:
        return {}

    conversation_lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        conversation_lines.append(f"{role}: {content}")

    conversation_text = "\n".join(conversation_lines)

    extract_prompt = """You are a fact extractor for a personal AI assistant.

Read the conversation and extract key facts about the user as JSON key-value pairs.

Examples of facts to extract:
- "name": "jazii"
- "location": "lahore"
- "job": "vibe coder"
- "interests": "coding, AI bots"
- "sleep_habit": "sleeps past noon"
- "preferred_language": "english"

Only extract facts that were explicitly stated or clearly implied.
Return ONLY valid JSON with string keys and string values. No explanation.
If no facts found, return: {}
"""

    extract_messages = [{"role": "user", "content": f"Conversation:\n{conversation_text}\n\nExtract user facts as JSON:"}]

    result = ai_provider.chat(
        messages=extract_messages,
        system_prompt=extract_prompt,
        max_tokens=300,
        tier="fast",
    )

    if not result:
        return {}

    # Parse JSON from response
    try:
        import json
        # Clean up potential markdown wrapping
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        facts = json.loads(cleaned)
        if isinstance(facts, dict):
            return {str(k): str(v) for k, v in facts.items()}
    except Exception as e:
        logger.warning(f"Failed to parse extracted facts: {e}")

    return {}
