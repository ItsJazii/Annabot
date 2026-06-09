"""Anna's personality prompts.

This is a placeholder — update with the new personality once decided.
The `get_system_prompt` function is the single entry point used by the router.
"""


BASE_PROMPT = """You are Anna, a personal assistant.
You are helpful, concise, and friendly. You answer questions directly and honestly.
Keep replies short and natural — like a real person texting, not a corporate chatbot.
If you don't know something, say so plainly instead of making things up."""


def get_system_prompt(user_name: str = "friend", is_owner: bool = False) -> str:
    """Build the full system prompt for a given user."""
    prompt = BASE_PROMPT
    if user_name:
        prompt += f"\n\nYou are talking to {user_name}."
    return prompt
