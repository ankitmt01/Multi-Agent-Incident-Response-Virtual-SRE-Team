from typing import List
import hashlib

def _hash_token(token: str, dim: int) -> int:
    h = hashlib.sha1(token.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % dim

def embed_texts(texts: List[str], dim: int = 256) -> List[List[float]]:
    vecs = []
    for t in texts:
        v = [0.0] * dim
        tokens = [tok for tok in t.lower().split() if tok.strip()]
        for tok in tokens:
            idx = _hash_token(tok, dim)
            v[idx] += 1.0
        # L2 normalize
        norm = sum(x*x for x in v) ** 0.5 or 1.0
        v = [x / norm for x in v]
        vecs.append(v)
    return vecs
