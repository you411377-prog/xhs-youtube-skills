from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ScrapedContent:
    platform: str
    content_id: str
    url: str
    title: str = ""
    content: str = ""
    content_type: str = "video"
    author_name: str = ""
    publish_time: Optional[datetime] = None
    like_count: int = 0
    comment_count: int = 0
    collect_count: int = 0
    tags: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class Summary:
    analysis: str = ""
