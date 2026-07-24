"""
Embeddings provider stub for future vector search integration.
Implementors may plug in OpenAI, local models, or FAISS-backed search.
"""
from typing import List


class EmbeddingsProvider:
    def __init__(self):
        raise NotImplementedError("Embeddings provider not implemented yet")

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def store_embeddings(self, ids: List[int], vectors: List[List[float]]):
        raise NotImplementedError

    def query(self, vector: List[float], top_k: int = 5):
        raise NotImplementedError
