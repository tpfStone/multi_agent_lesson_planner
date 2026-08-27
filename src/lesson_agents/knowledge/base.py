from __future__ import annotations

from typing import Protocol


class KnowledgeRetriever(Protocol):
    def retrieve(
        self,
        *,
        subject: str,
        grade: str,
        topic: str,
        query: str,
    ) -> list[dict]: ...

