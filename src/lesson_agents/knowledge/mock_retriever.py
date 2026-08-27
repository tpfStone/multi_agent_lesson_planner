from __future__ import annotations


class MockRetriever:
    """Phase 1 placeholder retriever; it performs no search or RAG."""

    def __init__(self, results: list[dict] | None = None) -> None:
        self._results = list(results or [])

    def retrieve(
        self,
        *,
        subject: str,
        grade: str,
        topic: str,
        query: str,
    ) -> list[dict]:
        del subject, grade, topic, query
        return list(self._results)

