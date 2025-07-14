# For future use: input sanitization, logging, etc.

def sanitize_input(text: str) -> str:
    return text.strip().replace("\n", " ")
