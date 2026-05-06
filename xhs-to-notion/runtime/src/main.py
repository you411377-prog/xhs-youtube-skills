"""
社媒笔记助手 CLI

用法:
  python -m src.main --doctor
  python -m src.main "https://www.xiaohongshu.com/explore/xxxxx"
  python -m src.main --file links.txt
  python -m src.main --export notion "https://www.xiaohongshu.com/explore/xxxxx"
  python -m src.main --check-cookies
  python -m src.main --no-summary "https://www.xiaohongshu.com/explore/xxxxx"
"""

import argparse
import sys
import time
from pathlib import Path

import yaml

from src.artifacts import read_artifact_bundle, write_artifact_bundle
from src.router import parse_link, Platform
from src.scrapers.base import BaseScraper
from src.scrapers.xiaohongshu import XiaohongshuScraper
from src.summarizer.ai_summarizer import AISummarizer, Summary
from src.exporters.notion import NotionExporter
from src.youtube_novel import read_youtube_novel_artifact
from src.utils.cookie_manager import CookieManager
from src.utils.logger import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / ".trae_artifacts" / "xhs_to_notion" / "latest"


def load_config(path: str | None = None) -> dict:
    if path is None:
        path = PROJECT_ROOT / "config" / "config.yaml"
    config_path = Path(path)
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        logger.info("请复制 config/config.example.yaml 为 config/config.yaml 并填入你的配置")
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def resolve_cookie_path(config_path: str) -> str:
    p = Path(config_path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return str(p)


def resolve_artifact_dir(path: str | None = None) -> Path:
    if path is None:
        return DEFAULT_ARTIFACT_DIR.resolve()
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve()


def _has_value(value) -> bool:
    if value is None:
        return False
    if not isinstance(value, str):
        return True
    stripped = value.strip()
    if not stripped:
        return False
    placeholder_markers = (
        "xxxxx",
        "your_",
        "替换",
        "example",
        "sk-xxxxx",
        "ntn_xxxxx",
    )
    return not any(marker in stripped for marker in placeholder_markers)


def _check_config_readiness(config: dict) -> tuple[list[str], list[str]]:
    ok_items: list[str] = []
    missing_items: list[str] = []

    xhs_cookie_path = resolve_cookie_path(config.get("cookies", {}).get("xiaohongshu", ""))
    xhs_cookie_file = Path(xhs_cookie_path)
    if xhs_cookie_file.exists():
        ok_items.append(f"已找到小红书 Cookie 文件: {xhs_cookie_path}")
    else:
        missing_items.append(
            "缺少小红书 Cookie 文件。请把浏览器导出的 Cookie JSON 放到 "
            f"{xhs_cookie_path}"
        )

    ai_cfg = config.get("ai", {})
    provider = ai_cfg.get("provider", "deepseek")
    provider_cfg = ai_cfg.get(provider, {})
    if provider in ("deepseek", "openai") and _has_value(provider_cfg.get("api_key")):
        ok_items.append(f"AI 已配置: provider={provider}")
    else:
        ok_items.append(
            "脚本内 AI 未配置；这不影响 Skill / Agent 架构，可由 Trae 内置 AI 完成总结"
        )

    gemini_cfg = ai_cfg.get("gemini", {})
    if _has_value(gemini_cfg.get("api_key")):
        ok_items.append("图片分析已配置 Gemini / OpenRouter key")
    else:
        missing_items.append(
            "图片分析是可选项，目前未配置 gemini.api_key；不影响基础抓取和 Notion 归档"
        )

    export_cfg = config.get("export", {})
    target = export_cfg.get("target", "notion")
    if target in ("notion", "both"):
        notion_cfg = export_cfg.get("notion", {})
        notion_key_ok = _has_value(notion_cfg.get("api_key"))
        notion_db_ok = _has_value(notion_cfg.get("database_id"))
        if notion_key_ok and notion_db_ok:
            ok_items.append("Notion 导出配置已填写")
        else:
            missing_items.append(
                "Notion 未配置完成。请填写 export.notion.api_key 和 export.notion.database_id"
            )
    else:
        missing_items.append(
            "当前 export.target 不是 notion。这个项目目前只完整支持 Notion 导出"
        )

    return ok_items, missing_items


def doctor(config: dict):
    logger.info("开始环境体检...")
    ok_items, missing_items = _check_config_readiness(config)

    for item in ok_items:
        logger.info(f"[通过] {item}")
    for item in missing_items:
        logger.warning(f"[待补充] {item}")

    if any("Cookie 文件" in item for item in ok_items):
        logger.info("继续检查 Cookie 是否有效...")
        check_cookies(config)

    notion_cfg = config.get("export", {}).get("notion", {})
    if _has_value(notion_cfg.get("api_key")) and _has_value(notion_cfg.get("database_id")):
        try:
            exporter = NotionExporter(
                notion_cfg["api_key"],
                notion_cfg["database_id"],
            )
            schema = exporter._get_schema()
            logger.info(f"[通过] Notion 数据库可访问，属性数: {len(schema)}")
        except Exception as e:
            logger.warning(f"[待补充] Notion 数据库访问失败: {e}")

    if missing_items:
        logger.warning("环境体检未全部通过。把上面的待补充项发给我，我可以继续替你接。")
    else:
        logger.info("环境体检通过，可以开始处理真实小红书链接。")


def get_scraper(platform: Platform, config: dict) -> BaseScraper:
    if platform == Platform.XIAOHONGSHU:
        cookie_path = resolve_cookie_path(config["cookies"]["xiaohongshu"])
        return XiaohongshuScraper(cookie_path, config)
    elif platform == Platform.DOUYIN:
        raise NotImplementedError("抖音采集器将在 Phase 2 实现")
    else:
        raise ValueError(f"不支持的平台: {platform}")


def get_exporters(
    config: dict,
    export_override: str | None = None,
    notion_api_key_override: str | None = None,
    notion_database_id_override: str | None = None,
):
    export_cfg = config.get("export", {})
    target = export_override or export_cfg.get("target", "notion")
    exporters = []

    if target in ("notion", "both"):
        notion_cfg = export_cfg.get("notion", {})
        notion_api_key = notion_api_key_override or notion_cfg["api_key"]
        notion_database_id = notion_database_id_override or notion_cfg["database_id"]
        exporters.append(
            NotionExporter(notion_api_key, notion_database_id)
        )

    if target in ("feishu", "both"):
        raise NotImplementedError("飞书导出器将在 Phase 2 实现")

    return exporters


def build_optional_summarizer(config: dict, force_disable: bool = False) -> AISummarizer | None:
    if force_disable:
        return None
    ai_cfg = config.get("ai", {})
    provider = ai_cfg.get("provider", "deepseek")
    provider_cfg = ai_cfg.get(provider, {})
    if provider in ("deepseek", "openai") and _has_value(provider_cfg.get("api_key")):
        return AISummarizer(config)
    logger.info("未配置脚本内 AI，将跳过代码内总结；可改用 Trae Skill / Agent 总结")
    return None


def get_urls(args) -> list[str]:
    urls = []
    if args.url:
        urls.append(args.url)
    if args.file:
        with open(args.file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    return urls


def check_cookies(config: dict):
    cm = CookieManager()
    for platform in ["douyin", "xiaohongshu"]:
        cookie_path = resolve_cookie_path(config["cookies"].get(platform, ""))
        p = Path(cookie_path)
        if not p.exists():
            logger.warning(f"[{platform}] Cookie 文件不存在: {cookie_path}")
            continue
        cookies = cm.load(cookie_path)
        checker = cm.check_douyin if platform == "douyin" else cm.check_xiaohongshu
        if checker(cookies):
            logger.info(f"[{platform}] Cookie 有效")
        else:
            logger.warning(f"[{platform}] Cookie 可能已过期，请重新导出")


def fetch_content(url: str, config: dict):
    logger.info(f"处理链接: {url}")

    parsed = parse_link(url)
    if parsed.platform == Platform.UNKNOWN:
        logger.warning(f"无法识别的链接: {url}")
        return None
    logger.info(f"识别: {parsed.platform.value} | ID: {parsed.content_id}")

    scraper = get_scraper(parsed.platform, config)
    try:
        content = scraper.fetch(parsed.content_id, parsed.xsec_token, parsed.xsec_source)
    finally:
        if hasattr(scraper, "close"):
            scraper.close()
    return content


def export_content(content, exporters: list, summary_text: str | None):
    page_urls = []
    summary = Summary(analysis=summary_text or content.content)
    for exporter in exporters:
        try:
            page_url = exporter.export(content, summary)
            logger.info(f"归档成功: {page_url}")
            page_urls.append(page_url)
        except Exception as e:
            logger.error(f"导出失败 [{type(exporter).__name__}]: {e}")
    return page_urls


def process_url(url: str, config: dict, summarizer: AISummarizer | None,
                exporters: list, delay: int):
    content = fetch_content(url, config)
    if content is None:
        return

    image_analysis = ""
    if content.image_urls and config.get("ai", {}).get("gemini", {}).get("api_key"):
        try:
            from src.analyzer.image_analyzer import ImageAnalyzer
            analyzer = ImageAnalyzer(config)
            image_analysis = analyzer.analyze_images(content.image_urls)
        except Exception as e:
            logger.warning(f"图片分析失败: {e}")

    summary_text = None
    if summarizer:
        summary = summarizer.summarize(content, image_analysis)
        summary_text = summary.analysis
        preview = summary_text[:80].replace("\n", " ")
        logger.info(f"AI 分析: {preview}...")

    export_content(content, exporters, summary_text)
    time.sleep(delay)


def fetch_to_artifact(url: str, config: dict, artifact_dir: str | None = None,
                      download_images: bool = True):
    content = fetch_content(url, config)
    if content is None:
        return None
    target_dir = resolve_artifact_dir(artifact_dir)
    timeout = config.get("request", {}).get("timeout", 20)
    bundle_dir = write_artifact_bundle(
        content,
        target_dir,
        download_images=download_images,
        timeout=timeout,
    )
    logger.info(f"抓取产物已写入: {bundle_dir}")
    logger.info(f"正文文件: {bundle_dir / 'source.md'}")
    logger.info(f"结构化数据: {bundle_dir / 'content.json'}")
    return bundle_dir


def export_from_artifact(config: dict, artifact_dir: str, summary_file: str | None,
                         export_override: str | None = None,
                         notion_api_key_override: str | None = None,
                         notion_database_id_override: str | None = None):
    bundle_dir = resolve_artifact_dir(artifact_dir)
    content, _ = read_artifact_bundle(bundle_dir)
    summary_text = None
    if summary_file:
        summary_text = Path(summary_file).expanduser().read_text(encoding="utf-8").strip()
        logger.info(f"已读取 Agent 总结: {summary_file}")
    exporters = get_exporters(
        config,
        export_override,
        notion_api_key_override,
        notion_database_id_override,
    )
    return export_content(content, exporters, summary_text)


def export_youtube_novel(
    config: dict,
    artifact_dir: str,
    novel_file: str | None,
    export_override: str | None = None,
    notion_api_key_override: str | None = None,
    notion_database_id_override: str | None = None,
):
    content, summary_text = read_youtube_novel_artifact(artifact_dir, novel_file)
    exporters = get_exporters(
        config,
        export_override,
        notion_api_key_override,
        notion_database_id_override,
    )
    return export_content(content, exporters, summary_text)


def main():
    parser = argparse.ArgumentParser(
        description="社媒笔记助手 — 采集抖音/小红书内容，AI 总结，归档到 Notion/飞书"
    )
    parser.add_argument("url", nargs="?", help="要处理的链接")
    parser.add_argument("--file", "-f", help="批量处理：从文件读取链接（每行一个）")
    parser.add_argument("--export", "-e", choices=["notion", "feishu", "both"],
                        default=None, help="归档目标（覆盖配置文件设置）")
    parser.add_argument("--no-summary", action="store_true", help="跳过 AI 总结")
    parser.add_argument("--check-cookies", action="store_true", help="检查 Cookie 状态")
    parser.add_argument("--doctor", action="store_true", help="检查真实环境是否已配置完成")
    parser.add_argument("--fetch-only", action="store_true", help="只抓取并输出本地产物，供 Skill / Agent 总结")
    parser.add_argument("--artifact-dir", default=None, help="抓取产物目录，默认写入 .trae_artifacts/xhs_to_notion/latest")
    parser.add_argument("--summary-file", default=None, help="由 Agent 生成的总结 Markdown 文件")
    parser.add_argument("--export-from-artifact", action="store_true", help="从抓取产物和总结文件归档到 Notion")
    parser.add_argument("--export-youtube-novel", action="store_true", help="从 YouTube 小说产物目录归档到 Notion")
    parser.add_argument("--novel-file", default=None, help="YouTube 小说 Markdown 文件；默认自动选择产物目录里最新的 .md")
    parser.add_argument("--notion-api-key", default=None, help="临时覆盖配置文件中的 Notion API key")
    parser.add_argument("--notion-database-id", default=None, help="临时覆盖配置文件中的 Notion database id")
    parser.add_argument("--skip-image-download", action="store_true", help="抓取产物时不下载图片到本地")
    parser.add_argument("--config", "-c", default=None, help="配置文件路径")
    args = parser.parse_args()

    if (
        not args.check_cookies
        and not args.doctor
        and not args.fetch_only
        and not args.export_from_artifact
        and not args.export_youtube_novel
        and not args.url
        and not args.file
    ):
        parser.print_help()
        sys.exit(1)

    # Load config
    config = load_config(args.config)
    delay = config.get("request", {}).get("delay_seconds", 3)

    if args.check_cookies:
        check_cookies(config)
        return
    if args.doctor:
        doctor(config)
        return
    if args.fetch_only:
        if not args.url:
            logger.error("--fetch-only 模式需要提供链接")
            sys.exit(1)
        fetch_to_artifact(
            args.url,
            config,
            artifact_dir=args.artifact_dir,
            download_images=not args.skip_image_download,
        )
        return
    if args.export_from_artifact:
        export_from_artifact(
            config,
            artifact_dir=args.artifact_dir or str(DEFAULT_ARTIFACT_DIR),
            summary_file=args.summary_file,
            export_override=args.export,
            notion_api_key_override=args.notion_api_key,
            notion_database_id_override=args.notion_database_id,
        )
        return
    if args.export_youtube_novel:
        if not args.artifact_dir:
            logger.error("--export-youtube-novel 模式需要提供 --artifact-dir")
            sys.exit(1)
        export_youtube_novel(
            config,
            artifact_dir=args.artifact_dir,
            novel_file=args.novel_file,
            export_override=args.export,
            notion_api_key_override=args.notion_api_key,
            notion_database_id_override=args.notion_database_id,
        )
        return

    summarizer = build_optional_summarizer(config, force_disable=args.no_summary)
    exporters = get_exporters(config, args.export)

    urls = get_urls(args)
    success = 0
    failed = 0
    for i, url in enumerate(urls):
        try:
            process_url(url, config, summarizer, exporters, delay)
            success += 1
        except Exception as e:
            logger.error(f"处理失败 [{url[:60]}...]: {e}")
            failed += 1
        if i < len(urls) - 1:
            time.sleep(delay)

    # Summary
    logger.info(f"处理完成: 成功 {success}, 失败 {failed}")


if __name__ == "__main__":
    main()
