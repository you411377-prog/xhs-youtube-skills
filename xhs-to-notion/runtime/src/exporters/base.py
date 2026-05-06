from abc import ABC, abstractmethod
from src.scrapers.base import ScrapedContent


class BaseExporter(ABC):

    @abstractmethod
    def export(self, content: ScrapedContent, summary: "Summary") -> str:
        ...
