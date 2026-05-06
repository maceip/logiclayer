from __future__ import annotations

import math
from typing import Sequence


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def embed_texts_sync(client: object, model: str, texts: list[str]) -> list[list[float]]:
    """OpenAI embeddings; returns one vector per text (same order)."""
    from openai import OpenAI

    assert isinstance(client, OpenAI)
    out: list[list[float]] = []
    batch = 64
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        resp = client.embeddings.create(model=model, input=chunk)
        for item in sorted(resp.data, key=lambda x: x.index):
            out.append(list(item.embedding))
    return out
