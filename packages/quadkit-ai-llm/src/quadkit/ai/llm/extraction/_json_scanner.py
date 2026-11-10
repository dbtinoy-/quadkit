from __future__ import annotations


def extract_json_objects(text: str) -> list[str]:
    """Extract all valid JSON objects from a string using bracket counting.

    Correctly handles nested objects and arrays, unlike regex approaches
    that stop at the first closing brace.

    Args:
        text: Input string that may contain embedded JSON objects.

    Returns:
        List of valid JSON object strings found in the text.
    """
    from quadkit.serialization import JSONDecodeError, loads

    results: list[str] = []
    i = 0
    length = len(text)

    while i < length:
        if text[i] != "{":
            i += 1
            continue

        depth = 0
        in_string = False
        escape_next = False
        j = i

        while j < length:
            ch = text[j]

            if escape_next:
                escape_next = False
                j += 1
                continue

            if ch == "\\" and in_string:
                escape_next = True
                j += 1
                continue

            if ch == '"':
                in_string = not in_string
            elif not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[i : j + 1]
                        try:
                            loads(candidate)
                            results.append(candidate)
                        except (ValueError, TypeError, JSONDecodeError):
                            pass
                        i = j + 1
                        break

            j += 1
        else:
            # Ran out of characters without closing brace — skip this opening
            i += 1

    return results
