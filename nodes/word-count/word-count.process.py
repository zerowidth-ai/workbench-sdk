from typing import Any
import re


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    text = inputs.get("text")

    if not isinstance(text, str) or text == "":
        return {
            "characters": 0,
            "characters_no_spaces": 0,
            "words": 0,
            "sentences": 0,
            "paragraphs": 0,
            "lines": 0,
        }

    # Character counts
    characters = len(text)
    characters_no_spaces = len(re.sub(r"\s", "", text))

    # Word count - split on whitespace and filter empty
    word_list = text.strip().split()
    words = len([w for w in word_list if len(w) > 0])

    # Sentence count - split on sentence-ending punctuation
    sentence_matches = re.findall(r"[.!?]+(?:\s|$)", text)
    sentences = len(sentence_matches) if sentence_matches else (1 if text.strip() else 0)

    # Paragraph count - split on double newlines
    paragraph_list = re.split(r"\n\s*\n", text)
    paragraphs = len([p for p in paragraph_list if p.strip()])

    # Line count
    lines = len(text.split("\n"))

    return {
        "characters": characters,
        "characters_no_spaces": characters_no_spaces,
        "words": words,
        "sentences": sentences,
        "paragraphs": paragraphs,
        "lines": lines,
    }
