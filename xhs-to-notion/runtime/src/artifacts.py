import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.scrapers.base import ScrapedContent


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _deserialize_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def serialize_scraped_content(content: ScrapedContent) -> dict:
    return {
        "platform": content.platform,
        "content_id": content.content_id,
        "url": content.url,
        "title": content.title,
        "content": content.content,
        "content_type": content.content_type,
        "author_name": content.author_name,
        "author_id": content.author_id,
        "publish_time": _serialize_datetime(content.publish_time),
        "like_count": content.like_count,
        "comment_count": content.comment_count,
        "share_count": content.share_count,
        "collect_count": content.collect_count,
        "tags": content.tags,
        "image_urls": content.image_urls,
        "video_url": content.video_url,
        "extra": content.extra,
    }


def deserialize_scraped_content(data: dict) -> ScrapedContent:
    return ScrapedContent(
        platform=data.get("platform", ""),
        content_id=data.get("content_id", ""),
        url=data.get("url", ""),
        title=data.get("title", ""),
        content=data.get("content", ""),
        content_type=data.get("content_type", "image_text"),
        author_name=data.get("author_name", ""),
        author_id=data.get("author_id", ""),
        publish_time=_deserialize_datetime(data.get("publish_time")),
        like_count=data.get("like_count", 0),
        comment_count=data.get("comment_count", 0),
        share_count=data.get("share_count", 0),
        collect_count=data.get("collect_count", 0),
        tags=data.get("tags", []),
        image_urls=data.get("image_urls", []),
        video_url=data.get("video_url"),
        extra=data.get("extra", {}),
    )


def _guess_suffix(url: str) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".jpg"


def _download_images(image_urls: list[str], images_dir: Path, timeout: int = 20) -> list[str]:
    local_paths: list[str] = []
    images_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.xiaohongshu.com/",
    }
    for index, url in enumerate(image_urls, start=1):
        suffix = _guess_suffix(url)
        target = images_dir / f"image_{index:02d}{suffix}"
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        target.write_bytes(response.content)
        local_paths.append(str(target.resolve()))
    return local_paths


def _render_source_markdown(content: ScrapedContent, local_image_paths: list[str]) -> str:
    top_comments = (content.extra or {}).get("top_comments", [])
    lines = [
        "# 小红书抓取结果",
        "",
        f"- 标题：{content.title or '(无标题)'}",
        f"- 作者：{content.author_name or '未知作者'}",
        f"- 原始链接：{content.url}",
        f"- 内容类型：{content.content_type}",
        f"- 点赞：{content.like_count}",
        f"- 评论：{content.comment_count}",
        f"- 收藏：{content.collect_count}",
        f"- 标签：{', '.join(content.tags) if content.tags else '(无)'}",
        f"- 图片数：{len(local_image_paths)}",
        "",
        "## 正文",
        "",
        content.content or "(无正文)",
        "",
    ]
    if top_comments:
        lines.extend(["## 评论区摘录", ""])
        for item in top_comments:
            author = item.get("author", "匿名")
            comment = item.get("content", "")
            lines.append(f"- {author}：{comment}")
        lines.append("")
    if local_image_paths:
        lines.extend(["## 本地图片", ""])
        lines.extend([f"- {path}" for path in local_image_paths])
        lines.append("")
    return "\n".join(lines)


def write_artifact_bundle(
    content: ScrapedContent,
    artifact_dir: str | Path,
    download_images: bool = True,
    timeout: int = 20,
) -> Path:
    artifact_path = Path(artifact_dir).expanduser().resolve()
    artifact_path.mkdir(parents=True, exist_ok=True)
    local_image_paths: list[str] = []
    if download_images and content.image_urls:
        local_image_paths = _download_images(content.image_urls, artifact_path / "images", timeout)

    manifest = {
        "content": serialize_scraped_content(content),
        "local_image_paths": local_image_paths,
    }
    (artifact_path / "content.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (artifact_path / "source.md").write_text(
        _render_source_markdown(content, local_image_paths),
        encoding="utf-8",
    )
    return artifact_path


def read_artifact_bundle(artifact_dir: str | Path) -> tuple[ScrapedContent, list[str]]:
    artifact_path = Path(artifact_dir).expanduser().resolve()
    manifest = json.loads((artifact_path / "content.json").read_text(encoding="utf-8"))
    content = deserialize_scraped_content(manifest["content"])
    local_image_paths = manifest.get("local_image_paths", [])
    return content, local_image_paths
