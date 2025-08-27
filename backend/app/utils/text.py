from __future__ import annotations
from typing import Iterable

def make_snippet(text: str, terms: Iterable[str], max_len: int = 260) -> str:
    if not text:
        return ""
    t = text
    # Find first occurrence of any term (case-insensitive)
    hit = None
    for term in terms:
        if not term:
            continue
        i = t.lower().find(term.lower())
        if i != -1 and (hit is None or i < hit):
            hit = i
    if hit is None:
        # no term found; just head of doc
        return t.strip().replace("\n", " ")[:max_len]
    start = max(0, hit - max_len // 3)
    end = min(len(t), start + max_len)
    snippet = t[start:end].strip().replace("\n", " ")
    if start > 0:
        snippet = "…" + snippet
    if end < len(t):
        snippet = snippet + "…"
    return snippet
