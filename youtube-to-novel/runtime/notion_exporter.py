import logging
import re
from datetime import datetime

import requests

try:
    from .models import ScrapedContent, Summary
except ImportError:
    from models import ScrapedContent, Summary

logger = logging.getLogger(__name__)


def markdown_to_notion_blocks(text: str) -> list[dict]:
    blocks = []
    buf: list[str] = []

    def flush_paragraph():
        nonlocal buf
        if buf:
            para_text = " ".join(buf)
            for chunk in _split_rich_text(para_text):
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": chunk}}]},
                })
            buf.clear()

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            flush_paragraph()
            i += 1
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)", line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            block_type = f"heading_{min(level, 3)}"
            blocks.append({
                "object": "block",
                "type": block_type,
                block_type: {"rich_text": [{"text": {"content": content[:2000]}}]},
            })
            i += 1
            continue

        bullet_match = re.match(r"^[\-\*]\s+(.+)", line)
        if bullet_match:
            flush_paragraph()
            while i < len(lines) and re.match(r"^[\-\*]\s+(.+)", lines[i].strip()):
                current = re.match(r"^[\-\*]\s+(.+)", lines[i].strip())
                if current:
                    blocks.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"text": {"content": current.group(1)[:2000]}}],
                        },
                    })
                i += 1
            continue

        num_match = re.match(r"^\d+[\.\)]\s+(.+)", line)
        if num_match:
            flush_paragraph()
            while i < len(lines) and re.match(r"^\d+[\.\)]\s+(.+)", lines[i].strip()):
                current = re.match(r"^\d+[\.\)]\s+(.+)", lines[i].strip())
                if current:
                    blocks.append({
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {
                            "rich_text": [{"text": {"content": current.group(1)[:2000]}}],
                        },
                    })
                i += 1
            continue

        if line.startswith(">"):
            flush_paragraph()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip("> ").strip())
                i += 1
            quote_text = "\n".join(quote_lines)
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": [{"text": {"content": quote_text[:2000]}}]},
            })
            continue

        buf.append(line)
        i += 1

    flush_paragraph()
    return blocks


def _split_rich_text(text: str, limit: int = 2000) -> list[str]:
    if len(text) <= limit:
        return [text]
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def _chunk_items(items: list[dict], chunk_size: int = 100) -> list[list[dict]]:
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def _parse_multi_value(text: str) -> list[dict]:
    values: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ")):
            line = line[2:].strip()
        parts = re.split(r"[，,、/；;]", line)
        for part in parts:
            value = part.strip()
            if value and value not in values:
                values.append(value[:50])
    return [{"name": value} for value in values]


def _parse_sectioned_summary(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        heading_match = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if heading_match:
            current_key = heading_match.group(1).strip()
            sections.setdefault(current_key, [])
            continue
        if current_key is not None:
            sections[current_key].append(line)
    return {
        key: "\n".join(lines).strip()
        for key, lines in sections.items()
        if "\n".join(lines).strip()
    }


class NotionExporter:
    NOTION_API = "https://api.notion.com/v1"
    PLATFORM_LABELS = {"youtube": "YouTube"}

    def __init__(self, api_key: str, database_id: str):
        self.api_key = api_key
        self.database_id = database_id
        self._schema: dict | None = None

    def _api_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    def _get_schema(self) -> dict:
        if self._schema is None:
            resp = requests.get(
                f"{self.NOTION_API}/databases/{self.database_id}",
                headers=self._api_headers(),
                timeout=20,
            )
            resp.raise_for_status()
            self._schema = resp.json().get("properties", {})
            logger.info("Notion schema: %s", list(self._schema.keys()))
        return self._schema

    def export(self, content: ScrapedContent, summary: Summary) -> str:
        now = datetime.now()
        schema = self._get_schema()
        extra = content.extra or {}
        summary_sections = _parse_sectioned_summary(summary.analysis or "")

        title_prop = next(
            (name for name, info in schema.items() if info.get("type") == "title"),
            None,
        )
        title_text = f"[YouTube] {content.title[:80]}" if content.title else "[YouTube] 未命名"

        properties: dict = {}
        if title_prop:
            properties[title_prop] = {
                "title": [{"text": {"content": title_text[:100]}}],
            }

        meta_map = {
            "平台": ("select", {"name": "YouTube"}),
            "原视频链接": ("url", content.url),
            "视频时长": ("rich_text", [{"text": {"content": extra.get("duration_string", "")[:100]}}]),
            "实际字数": ("number", extra.get("novel_char_count")),
            "生成日期": ("date", {"start": now.isoformat()}),
            "一句话摘要": ("rich_text", [{"text": {"content": extra.get("novel_excerpt", "")[:2000]}}]),
            "小说类型": ("select", {"name": extra.get("genre", "")}),
            "叙事视角": ("select", {"name": extra.get("perspective", "")}),
            "文风": ("select", {"name": extra.get("style", "")}),
            "主题标签": ("multi_select", _parse_multi_value(summary_sections.get("主题标签", ""))),
        }

        for prop_name, (expected_type, value) in meta_map.items():
            if value in (None, "", []):
                continue
            if prop_name in schema and schema[prop_name].get("type") == expected_type:
                properties[prop_name] = {expected_type: value}

        if "阅读状态" in schema and schema["阅读状态"].get("type") == "select":
            properties["阅读状态"] = {"select": {"name": "未读"}}
        if "主题标签" in schema and schema["主题标签"].get("type") == "multi_select":
            default_tags = [{"name": "YouTube小说"}]
            video_title = (extra.get("video_title") or "").lower()
            if "ai" in video_title:
                default_tags.append({"name": "AI"})
            properties["主题标签"] = {"multi_select": default_tags}

        children = markdown_to_notion_blocks(summary.analysis)
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
            "children": children[:100],
        }

        resp = requests.post(
            f"{self.NOTION_API}/pages",
            headers=self._api_headers(),
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        page = resp.json()

        for batch in _chunk_items(children[100:]):
            append_resp = requests.patch(
                f"{self.NOTION_API}/blocks/{page['id']}/children",
                headers=self._api_headers(),
                json={"children": batch},
                timeout=20,
            )
            append_resp.raise_for_status()

        return page.get("url", "")
