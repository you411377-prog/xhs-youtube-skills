import argparse
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent))
    from artifact_reader import read_youtube_novel_artifact
    from models import Summary
    from notion_exporter import NotionExporter
else:
    from .artifact_reader import read_youtube_novel_artifact
    from .models import Summary
    from .notion_exporter import NotionExporter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 youtube-to-novel 产物目录导出到 Notion"
    )
    parser.add_argument("--artifact-dir", required=True, help="YouTube 小说产物目录")
    parser.add_argument("--novel-file", default=None, help="可选，显式指定小说 Markdown 文件")
    parser.add_argument("--notion-api-key", required=True, help="Notion internal integration token")
    parser.add_argument("--notion-database-id", required=True, help="目标 Notion database id")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    content, summary_text = read_youtube_novel_artifact(args.artifact_dir, args.novel_file)
    exporter = NotionExporter(
        api_key=args.notion_api_key,
        database_id=args.notion_database_id,
    )
    page_url = exporter.export(content, Summary(analysis=summary_text))
    print(page_url)


if __name__ == "__main__":
    main()
