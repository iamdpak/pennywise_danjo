from typing import Iterable
class EmbeddingIndex:
    def upsert_receipt(self, receipt_id: int, texts: Iterable[str]) -> None:
        pass
    def search(self, query: str, k: int = 10):
        return []
