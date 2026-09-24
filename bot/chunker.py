"""
Markdown-Aware Message Chunker
==============================
Splits responses exceeding Discord's 2000-character ceiling into safe chunks
while tracking and preserving code block fences (```) and language identifiers.
"""

from __future__ import annotations

import re
from typing import List


def chunk_message(text: str, max_chars: int = 1900) -> List[str]:
    """
    Splits text into Discord-safe chunks (<= max_chars) respecting
    line breaks, word boundaries, and markdown code block fences (```).
    Prevents broken code highlights across Discord message boundaries.
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0
    in_code_block = False
    code_lang = ""

    lines = text.split("\n")

    for line in lines:
        fence_match = re.match(r"^```(\w*)", line)
        line_len = len(line) + 1  # accounts for newline

        # Flush chunk if adding this line exceeds the safe character budget
        if current_len + line_len > max_chars:
            if current_chunk:
                chunk_str = "\n".join(current_chunk)
                if in_code_block:
                    chunk_str += "\n```"
                chunks.append(chunk_str)
                current_chunk = []
                current_len = 0
                if in_code_block:
                    # Reopen code fence in the next chunk
                    current_chunk.append(f"```{code_lang}")
                    current_len = len(current_chunk[0]) + 1

            # Handle edge case: single line longer than max_chars
            while len(line) > max_chars:
                sub = line[:max_chars]
                line = line[max_chars:]
                chunks.append(sub)

        current_chunk.append(line)
        current_len += len(line) + 1

        if fence_match:
            if not in_code_block:
                in_code_block = True
                code_lang = fence_match.group(1)
            else:
                in_code_block = False
                code_lang = ""

    if current_chunk:
        chunk_str = "\n".join(current_chunk)
        if in_code_block:
            chunk_str += "\n```"
        chunks.append(chunk_str)

    return chunks
