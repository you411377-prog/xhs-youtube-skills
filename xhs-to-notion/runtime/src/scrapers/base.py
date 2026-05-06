import json
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.utils.logger import logger


@dataclass
class ScrapedContent:
    platform: str
    content_id: str
    url: str
    title: str = ""
    content: str = ""
    content_type: str = "image_text"
    author_name: str = ""
    author_id: str = ""
    publish_time: Optional[datetime] = None
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    collect_count: int = 0
    tags: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    video_url: Optional[str] = None
    extra: dict = field(default_factory=dict)


class BaseScraper(ABC):

    def __init__(self, cookie_path: str, config: dict):
        self.cookies = self._load_cookies(cookie_path)
        self.config = config
        self.session = self._build_session()

    def _load_cookies(self, path: str) -> dict:
        with open(path, "r") as f:
            cookie_list = json.load(f)
        return {c["name"]: c["value"] for c in cookie_list}

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.cookies.update(self.cookies)
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        return s

    @abstractmethod
    def fetch(self, content_id: str) -> ScrapedContent:
        ...

    def check_cookie_valid(self) -> bool:
        return True
