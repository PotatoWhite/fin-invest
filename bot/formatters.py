"""Telegram message formatting utilities."""


def chunk_message(text: str, max_length: int = 4096) -> list[str]:
    """Split long messages into chunks that fit Telegram's limit."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Find a good split point (newline, then space)
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1 or split_at < max_length // 2:
            split_at = text.rfind(" ", 0, max_length)
        if split_at == -1:
            split_at = max_length

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()

    return chunks


def format_price_krw(value: float | None) -> str:
    if value is None:
        return "—"
    return f"₩{value:,.0f}"


def format_price_usd(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:,.2f}"


def format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def format_number(value: float | int | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.1f}조"
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:.0f}억"
    if abs(value) >= 10_000:
        return f"{value / 10_000:.0f}만"
    return f"{value:,.0f}"
