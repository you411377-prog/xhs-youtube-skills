import json
import re
from datetime import datetime
from pathlib import Path

from src.scrapers.base import ScrapedContent


def _parse_upload_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return None


def _pick_novel_file(artifact_dir: Path, novel_file: str | None = None) -> Path:
    if novel_file:
        candidate = Path(novel_file).expanduser()
        if not candidate.is_absolute():
            candidate = (artifact_dir / candidate).resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"小说文件不存在: {candidate}")
        return candidate

    candidates = [
        path for path in artifact_dir.glob("*.md")
        if path.name not in {"source.md", "summary.md"}
    ]
    if not candidates:
        raise FileNotFoundError(
            f"在 {artifact_dir} 中未找到小说 Markdown 文件，请通过 --novel-file 指定"
        )
    return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[0]


def _pick_transcript_file(artifact_dir: Path) -> Path | None:
    preferred_patterns = [
        "*.en-orig.srt",
        "*.zh-Hans.srt",
        "*.zh.srt",
        "*.en.srt",
        "*.srt",
    ]
    for pattern in preferred_patterns:
        matches = sorted(artifact_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def _read_transcript_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.isdigit() or "-->" in line:
            continue
        lines.append(line)
    return "\n".join(lines)


def _read_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_excerpt(text: str, limit: int = 180) -> str:
    parts: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line[0].isdigit() and ". " in line:
            continue
        parts.append(line)
    flat = " ".join(parts)
    return flat[:limit]


def _join_clauses(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]}和{parts[1]}"
    return "、".join(parts[:-1]) + "，以及" + parts[-1]


def _build_video_summary(info: dict, transcript_text: str) -> str:
    title = (info.get("title") or "").strip()
    lower = f"{title}\n{transcript_text}".lower()
    clauses: list[str] = []

    if "learn ai" in lower or "how to learn ai" in lower or "ai yet" in lower:
        clauses.append("普通人如何系统学习和使用 AI")
    if "pattern recognition" in lower or "token" in lower:
        clauses.append("AI 的基本原理")
    if "prompt" in lower:
        clauses.append("高质量提示词与 master/system prompt 的搭建方法")
    if "pull prompting" in lower or "push prompting" in lower:
        clauses.append("从 push prompting 转向 pull prompting 的思路")
    if "taste" in lower or "vision" in lower or "care" in lower or "future-proof" in lower:
        clauses.append("在 AI 时代建立不易被替代能力的方向")

    unique_clauses: list[str] = []
    for clause in clauses:
        if clause not in unique_clauses:
            unique_clauses.append(clause)

    if unique_clauses:
        return f"视频主要讲了{_join_clauses(unique_clauses)}。"

    clean_title = re.sub(r"\s+", " ", title).strip(" -:：")
    if clean_title:
        return f"视频围绕“{clean_title}”展开，梳理核心观点、关键方法与可落地的实践建议。"
    return "视频围绕核心观点、关键方法与可落地实践建议展开。"


def _build_summary_markdown(
    title: str,
    novel_text: str,
    info: dict,
    transcript_path: Path | None,
) -> str:
    compact_novel_text = _compact_markdown_for_notion(novel_text)
    metadata_lines: list[str] = [
        compact_novel_text,
    ]
    return "\n".join(metadata_lines).strip()


def _compact_markdown_for_notion(text: str) -> str:
    lines: list[str] = []
    paragraph_buf: list[str] = []

    def flush_paragraph():
        nonlocal paragraph_buf
        if paragraph_buf:
            lines.append(" ".join(paragraph_buf))
            lines.append("")
            paragraph_buf = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            flush_paragraph()
            lines.append(line)
            lines.append("")
            continue
        paragraph_buf.append(line)

    flush_paragraph()
    return "\n".join(lines).strip()


def read_youtube_novel_artifact(
    artifact_dir: str | Path,
    novel_file: str | None = None,
) -> tuple[ScrapedContent, str]:
    artifact_path = Path(artifact_dir).expanduser().resolve()
    if not artifact_path.exists():
        raise FileNotFoundError(f"YouTube 产物目录不存在: {artifact_path}")

    info = _read_json_if_exists(artifact_path / "info.json")
    metadata = _read_json_if_exists(artifact_path / "novel_metadata.json")

    novel_path = _pick_novel_file(artifact_path, novel_file)
    transcript_path = _pick_transcript_file(artifact_path)

    novel_text = novel_path.read_text(encoding="utf-8").strip()
    transcript_text = _read_transcript_text(transcript_path)
    title = novel_path.stem or info.get("title") or "未命名小说"

    content = ScrapedContent(
        platform="youtube",
        content_id=info.get("id", artifact_path.name),
        url=info.get("webpage_url") or "",
        title=title,
        content=transcript_text or info.get("description", ""),
        content_type="video",
        author_name=info.get("channel") or info.get("uploader", ""),
        publish_time=_parse_upload_date(info.get("upload_date")),
        tags=[],
        image_urls=[],
        extra={
            "video_title": info.get("title", ""),
            "duration_string": info.get("duration_string", ""),
            "view_count": info.get("view_count"),
            "novel_char_count": len(novel_text.replace("\n", "").replace(" ", "")),
            "novel_excerpt": _build_video_summary(info, transcript_text),
            "genre": metadata.get("genre", ""),
            "perspective": metadata.get("perspective", ""),
            "style": metadata.get("style", ""),
            "target_words": metadata.get("target_words"),
            "artifact_dir": str(artifact_path),
            "novel_file": str(novel_path),
            "transcript_file": str(transcript_path) if transcript_path else "",
            "metadata_file": str(artifact_path / "novel_metadata.json"),
        },
    )

    summary_markdown = _build_summary_markdown(title, novel_text, info, transcript_path)
    return content, summary_markdown
