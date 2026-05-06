import re
import requests
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse, parse_qs

from src.utils.logger import logger


MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.0 Mobile/15E148 Safari/604.1"
)


class Platform(Enum):
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    UNKNOWN = "unknown"


@dataclass
class ParsedLink:
    platform: Platform
    content_id: str
    original_url: str
    resolved_url: str = ""
    xsec_token: str = ""
    xsec_source: str = ""


_SHORT_DOMAINS = {"v.douyin.com", "xhslink.com"}

_DOUYIN_ID_PATTERN = re.compile(r"video/(\d+)")
_XHS_ID_PATTERN = re.compile(r"(?:explore|discovery/item|notes)/([a-f0-9]{24})")
_URL_PATTERN = re.compile(
    r'https?://[^\s"`\'<>一-鿿　-〿＀-￯]+'
)


def extract_url_from_text(text: str) -> str:
    match = _URL_PATTERN.search(text)
    if not match:
        return ""
    url = match.group(0)
    # Strip trailing punctuation that likely isn't part of the URL
    url = re.sub(r'[.,;:!?)\]}、。，．」]+$', '', url)
    return url


def resolve_short_url(short_url: str) -> str:
    headers = {"User-Agent": MOBILE_USER_AGENT}
    try:
        resp = requests.get(
            short_url, headers=headers,
            allow_redirects=False, timeout=10
        )
        location = resp.headers.get("Location", "")
        if location:
            if location.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(short_url)
                location = f"{parsed.scheme}://{parsed.netloc}{location}"
            return location
        return short_url
    except requests.RequestException:
        return short_url


def parse_link(raw_input: str) -> ParsedLink:
    url = extract_url_from_text(raw_input)
    if not url:
        return ParsedLink(Platform.UNKNOWN, "", raw_input)

    # Resolve short links
    resolved_url = url
    for domain in _SHORT_DOMAINS:
        if domain in url:
            resolved = resolve_short_url(url)
            if resolved != url:
                resolved_url = resolved
                logger.info(f"短链接解析: {url[:50]}... → {resolved_url[:80]}...")
            break

    # Douyin
    m = _DOUYIN_ID_PATTERN.search(resolved_url)
    if m:
        return ParsedLink(Platform.DOUYIN, m.group(1), url, resolved_url)

    # Xiaohongshu
    m = _XHS_ID_PATTERN.search(resolved_url)
    if m:
        parsed_url = urlparse(resolved_url)
        params = parse_qs(parsed_url.query)
        return ParsedLink(
            platform=Platform.XIAOHONGSHU,
            content_id=m.group(1),
            original_url=url,
            resolved_url=resolved_url,
            xsec_token=params.get("xsec_token", [""])[0],
            xsec_source=params.get("xsec_source", [""])[0],
        )

    return ParsedLink(Platform.UNKNOWN, "", url, resolved_url)
