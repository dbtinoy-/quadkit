"""Extraction and normalization of thinking blocks from LLM responses."""

from __future__ import annotations

from quadkit.ai.llm.thinking.patterns import THINKING_PATTERNS


def _extract_gemma_channel(text: str) -> tuple[str, str | None] | None:
    """Extract thinking from Gemma-4 channel format.

    Google's canonical format (from official Gemma-4 docs):
    ``<|channel>thought\\n...thinking...\\n<channel|>\\n...response...``

    The end token ``<channel|>`` (note: opposite direction from the start token)
    marks the boundary between thinking and response content.

    Gemma-4 26B/31B with thinking *disabled* still emits a ghost empty block:
    ``<|channel>thought\\n<channel|>\\n{json}`` — this is handled correctly since
    the thinking text between the markers is empty (returned as ``None``).

    Fallback paths for LM Studio GGUF variants that may use different separators:
    1. ``\\n<|channel>response\\n`` — seen in some GGUF chat templates
    2. ``\\n<|channel>output\\n`` — alternative GGUF chat template variant
    3. Bare format: no end marker, content starts directly at the first ``{``/``[``

    Args:
        text: Raw model output potentially containing a Gemma channel block.

    Returns:
        ``(clean_content, thinking_text)`` tuple, or ``None`` if no Gemma
        channel start marker (``<|channel>thought``) is found.
    """
    start_marker = "<|channel>thought"

    if start_marker not in text:
        return None

    start_pos = text.find(start_marker)
    thinking_start = start_pos + len(start_marker)
    after_start = text[thinking_start:]

    # --- Primary path: canonical <channel|> end token (Google official format) ---
    end_token = "<channel|>"  # noqa: S105  # marker string, not a credential
    end_pos = after_start.find(end_token)
    if end_pos != -1:
        thinking_text = after_start[:end_pos].strip()
        clean_content = after_start[end_pos + len(end_token) :].strip()
        return clean_content, thinking_text or None

    # --- Secondary paths: GGUF chat-template variants ---
    for sep in ("\n<|channel>response\n", "\n<|channel>output\n"):
        sep_pos = after_start.find(sep)
        if sep_pos != -1:
            thinking_text = after_start[:sep_pos].strip()
            clean_content = after_start[sep_pos + len(sep) :].strip()
            return clean_content, thinking_text or None

    # --- Tertiary fallback: no separator — look for first { or [ ---
    # Some LM Studio GGUF variants output thinking directly followed by JSON
    # with no channel separator between them.
    for json_char in ("{", "["):
        json_pos = after_start.find(json_char)
        if json_pos != -1:
            thinking_text = after_start[:json_pos].strip()
            clean_content = after_start[json_pos:].strip()
            if thinking_text:  # Only strip if there actually is thinking text
                return clean_content, thinking_text

    return None


def normalize_thinking_text(text: str) -> tuple[str, str | None]:
    """Extract thinking text from raw LLM output.

    Tries each pattern in THINKING_PATTERNS order. Returns (clean_content, thinking_text_or_None).
    clean_content has thinking block removed and is stripped.
    thinking_text is the raw thinking content (stripped), or None if not found.

    Pattern matching is by substring presence of start_marker (and end_marker after it),
    NOT by model name. The bare-closing-tag pattern (end_marker="</think>", no start)
    matches only when start_marker is NOT found but end_marker IS found — this covers
    models that output ...thinking...</think>\\nresponse.

    Falls back: after removing a thinking block, if clean_content is empty but thinking
    text was found, tries to extract from the first `{` or `[` in the original text to
    recover any JSON that may have been embedded.

    Args:
        text: Raw LLM response text, possibly containing inline thinking tags.

    Returns:
        A tuple of (clean_content, thinking_text_or_None).
        - clean_content: The response text with thinking stripped out, stripped of whitespace.
        - thinking_text_or_None: The thinking/reasoning text, or None if no thinking found.
    """
    for pattern in THINKING_PATTERNS:
        # Special handling for Gemma channel format
        if pattern.name == "gemma_channel":
            result = _extract_gemma_channel(text)
            if result is not None:
                clean_content, thinking_text = result
                # Fallback: if clean_content is empty but thinking exists, try JSON recovery
                if not clean_content and thinking_text:
                    # Try to find JSON starting with { or [
                    for json_char in ("{", "["):
                        json_pos = text.find(json_char)
                        if json_pos != -1:
                            clean_content = text[json_pos:].strip()
                            break
                return clean_content, thinking_text

        # For bare closing tag pattern, only match if start_marker not found
        elif pattern.start_marker == "":
            if pattern.end_marker in text:
                # Find the position of the end marker
                end_pos = text.find(pattern.end_marker)
                thinking_text = text[:end_pos].strip()
                clean_content = text[end_pos + len(pattern.end_marker) :].strip()

                # Fallback: if clean_content is empty but thinking exists, try JSON recovery
                if not clean_content and thinking_text:
                    # Try to find JSON starting with { or [
                    for json_char in ("{", "["):
                        json_pos = text.find(json_char)
                        if json_pos != -1:
                            clean_content = text[json_pos:].strip()
                            break

                return clean_content, thinking_text or None

        # For patterns with start markers, check both start and end are present
        elif pattern.start_marker in text:
            start_pos = text.find(pattern.start_marker)
            # Look for end marker after the start marker
            end_search_start = start_pos + len(pattern.start_marker)
            end_pos = text.find(pattern.end_marker, end_search_start)

            if end_pos != -1:
                # Extract thinking content (between markers)
                thinking_start = start_pos + len(pattern.start_marker)
                thinking_text = text[thinking_start:end_pos].strip()

                # Extract clean content (after end marker)
                if pattern.strip_end_marker:
                    clean_start = end_pos + len(pattern.end_marker)
                else:
                    clean_start = end_pos

                clean_content = text[clean_start:].strip()

                # Fallback: if clean_content is empty but thinking exists, try JSON recovery
                if not clean_content and thinking_text:
                    # Try to find JSON starting with { or [
                    after_thinking = text[clean_start:]
                    for json_char in ("{", "["):
                        json_pos = after_thinking.find(json_char)
                        if json_pos != -1:
                            clean_content = after_thinking[json_pos:].strip()
                            break

                return clean_content, thinking_text or None

    # No pattern matched
    return text, None


__all__ = ["normalize_thinking_text"]
