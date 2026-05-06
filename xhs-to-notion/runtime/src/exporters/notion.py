import re
import requests
from datetime import datetime
from notion_client import Client

from src.exporters.base import BaseExporter
from src.scrapers.base import ScrapedContent
from src.summarizer.ai_summarizer import Summary
from src.utils.logger import logger


def markdown_to_notion_blocks(text: str) -> list[dict]:
    """Convert markdown text to Notion blocks — line-by-line parsing."""
    blocks = []
    buf: list[str] = []

    def flush_paragraph():
        nonlocal buf
        if buf:
            para_text = " ".join(buf)
            for chunk in _split_rich_text(para_text):
                blocks.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
                })
            buf.clear()

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines — flush pending paragraph
        if not line:
            flush_paragraph()
            i += 1
            continue

        # Heading: ### / ## / #
        heading_match = re.match(r"^(#{1,3})\s+(.+)", line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            blocks.append({
                "object": "block", "type": f"heading_{min(level, 3)}",
                f"heading_{min(level, 3)}": {
                    "rich_text": [{"text": {"content": content[:2000]}}]
                }
            })
            i += 1
            continue

        # Bullet list — collect consecutive bullet lines
        bullet_match = re.match(r"^[\-\*]\s+(.+)", line)
        if bullet_match:
            flush_paragraph()
            while i < len(lines) and re.match(r"^[\-\*]\s+(.+)", lines[i].strip()):
                bm = re.match(r"^[\-\*]\s+(.+)", lines[i].strip())
                if bm:
                    blocks.append({
                        "object": "block", "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"text": {"content": bm.group(1)[:2000]}}]
                        }
                    })
                i += 1
            continue

        # Numbered list
        num_match = re.match(r"^\d+[\.\)]\s+(.+)", line)
        if num_match:
            flush_paragraph()
            while i < len(lines) and re.match(r"^\d+[\.\)]\s+(.+)", lines[i].strip()):
                nm = re.match(r"^\d+[\.\)]\s+(.+)", lines[i].strip())
                if nm:
                    blocks.append({
                        "object": "block", "type": "numbered_list_item",
                        "numbered_list_item": {
                            "rich_text": [{"text": {"content": nm.group(1)[:2000]}}]
                        }
                    })
                i += 1
            continue

        # Quote
        if line.startswith(">"):
            flush_paragraph()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip("> ").strip())
                i += 1
            quote_text = "\n".join(quote_lines)
            blocks.append({
                "object": "block", "type": "quote",
                "quote": {"rich_text": [{"text": {"content": quote_text[:2000]}}]}
            })
            continue

        # Regular paragraph line — accumulate
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


def _first_line(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line:
            return line
    return ""


class NotionExporter(BaseExporter):

    NOTION_API = "https://api.notion.com/v1"
    PLATFORM_LABELS = {
        "xiaohongshu": "小红书",
        "douyin": "抖音",
        "youtube": "YouTube",
    }

    def __init__(self, api_key: str, database_id: str):
        self.client = Client(auth=api_key)
        self.database_id = database_id
        self.api_key = api_key
        self._schema = None

    def _api_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
        }

    def _get_schema(self) -> dict:
        if self._schema is None:
            try:
                resp = requests.get(
                    f"{self.NOTION_API}/databases/{self.database_id}",
                    headers=self._api_headers(),
                    timeout=10,
                )
                resp.raise_for_status()
                self._schema = resp.json().get("properties", {})
            except Exception as e:
                logger.warning(f"获取数据库 schema 失败: {e}")
                self._schema = {"名称": {"type": "title", "title": {}}}
            logger.info(f"Notion 数据库属性: {list(self._schema.keys())}")
        return self._schema

    def _has_prop(self, name: str) -> bool:
        return name in self._get_schema()

    def export(self, content: ScrapedContent, summary: Summary) -> str:
        now = datetime.now()
        schema = self._get_schema()
        platform_name = self.PLATFORM_LABELS.get(content.platform, content.platform or "未知平台")
        extra = content.extra or {}
        summary_sections = _parse_sectioned_summary(summary.analysis or "")

        # Find title property
        title_prop = None
        for prop_name, prop_info in schema.items():
            if prop_info.get("type") == "title":
                title_prop = prop_name
                break

        # Build title: [平台] 标题
        title_text = f"[{platform_name}] {content.title[:80]}" if content.title else "(无标题)"

        properties = {}
        if title_prop:
            properties[title_prop] = {
                "title": [{"text": {"content": title_text[:100]}}]
            }

        # Metadata properties — all from ScrapedContent, not from AI
        meta_map = {
            "平台": ("select", {"name": platform_name}),
            "作者": ("rich_text", [{"text": {"content": content.author_name[:100]}}]),
            "原始链接": ("url", content.url),
            "发布时间": ("date", {
                "start": (
                    content.publish_time.isoformat()
                    if content.publish_time else now.strftime("%Y-%m-%d")
                )
            }),
            "点赞数": ("number", content.like_count),
            "评论数": ("number", content.comment_count),
            "收藏数": ("number", content.collect_count),
            "标签": ("multi_select", [
                {"name": t[:50]} for t in content.tags[:10]
            ]),
            "采集时间": ("date", {"start": now.isoformat()}),
            "原视频链接": ("url", content.url),
            "视频时长": ("rich_text", [{"text": {"content": extra.get("duration_string", "")[:100]}}]),
            "实际字数": ("number", extra.get("novel_char_count")),
            "生成日期": ("date", {"start": now.isoformat()}),
            "一句话摘要": ("rich_text", [{"text": {"content": extra.get("novel_excerpt", "")[:2000]}}]),
            "小说类型": ("select", {"name": extra.get("genre", "")}),
            "叙事视角": ("select", {"name": extra.get("perspective", "")}),
            "文风": ("select", {"name": extra.get("style", "")}),
            "一句话观点": ("rich_text", [{"text": {"content": summary_sections.get("一句话观点", "")[:2000]}}]),
            "核心问题": ("rich_text", [{"text": {"content": summary_sections.get("核心问题", "")[:2000]}}]),
            "关键结论": ("rich_text", [{"text": {"content": summary_sections.get("关键结论", "")[:2000]}}]),
            "可行动点": ("rich_text", [{"text": {"content": summary_sections.get("可行动点", "")[:2000]}}]),
            "知识类型": ("select", {"name": _first_line(summary_sections.get("知识类型", ""))[:100]}),
            "启发等级": ("select", {"name": _first_line(summary_sections.get("启发等级", ""))[:100]}),
            "复看状态": ("select", {"name": _first_line(summary_sections.get("复看状态", ""))[:100]}),
            "主题标签": ("multi_select", _parse_multi_value(summary_sections.get("主题标签", ""))),
            "适用场景": ("multi_select", _parse_multi_value(summary_sections.get("适用场景", ""))),
        }

        for prop_name, (expected_type, value) in meta_map.items():
            if value in (None, "", []):
                continue
            if prop_name in schema:
                prop_info = schema[prop_name]
                if prop_info.get("type") == expected_type:
                    properties[prop_name] = {expected_type: value}

        if content.platform == "youtube":
            if "阅读状态" in schema and schema["阅读状态"].get("type") == "select":
                properties["阅读状态"] = {"select": {"name": "未读"}}
            if "主题标签" in schema and schema["主题标签"].get("type") == "multi_select":
                default_tags = [{"name": "YouTube小说"}]
                video_title = (extra.get("video_title") or "").lower()
                if "ai" in video_title:
                    default_tags.append({"name": "AI"})
                properties["主题标签"] = {"multi_select": default_tags}

        # Build page children: AI analysis + divider + original content
        children = []

        # AI analysis — converted from markdown
        if summary.analysis:
            try:
                children.extend(markdown_to_notion_blocks(summary.analysis))
            except Exception as e:
                logger.warning(f"Markdown 转 Notion blocks 失败: {e}")
                children.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": summary.analysis[:2000]}}]}
                })

        if content.platform != "youtube":
            # Divider
            children.append({"object": "block", "type": "divider", "divider": {}})

            # Original content heading
            children.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "原始内容"}}]}
            })

            # Original content
            original_text = content.content or "(无内容)"
            for chunk in _split_rich_text(original_text):
                children.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
                })

        try:
            page = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
                children=children[:100],
            )

            for batch in _chunk_items(children[100:]):
                self.client.blocks.children.append(
                    block_id=page["id"],
                    children=batch,
                )

            page_url = page.get("url", "")
            logger.info(f"Notion 页面已创建: {page_url}")
            return page_url
        except Exception as e:
            logger.error(f"Notion 导出失败: {e}")
            raise
