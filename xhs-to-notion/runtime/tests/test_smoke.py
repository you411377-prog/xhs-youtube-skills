import tempfile
import unittest
from pathlib import Path

from src.artifacts import read_artifact_bundle, write_artifact_bundle
from src.main import _check_config_readiness, process_url
from src.router import Platform, parse_link
from src.scrapers.base import ScrapedContent


class RouterSmokeTest(unittest.TestCase):
    def test_parse_xiaohongshu_link(self):
        parsed = parse_link(
            "https://www.xiaohongshu.com/explore/0123456789abcdef01234567"
            "?xsec_token=abc&xsec_source=pc_feed"
        )
        self.assertEqual(parsed.platform, Platform.XIAOHONGSHU)
        self.assertEqual(parsed.content_id, "0123456789abcdef01234567")
        self.assertEqual(parsed.xsec_token, "abc")
        self.assertEqual(parsed.xsec_source, "pc_feed")


class ProcessUrlSmokeTest(unittest.TestCase):
    def test_process_url_without_summary_uses_placeholder_summary(self):
        import src.main as main_module

        content = ScrapedContent(
            platform="xiaohongshu",
            content_id="0123456789abcdef01234567",
            url="https://www.xiaohongshu.com/explore/0123456789abcdef01234567",
            title="测试标题",
            content="这是一条用于 smoke test 的正文。",
            author_name="测试作者",
        )

        exported = {}

        class FakeScraper:
            def fetch(self, content_id, xsec_token="", xsec_source=""):
                return content

            def close(self):
                return None

        class FakeExporter:
            def export(self, scraped_content, summary):
                exported["content"] = scraped_content
                exported["summary"] = summary
                return "https://notion.so/fake-page"

        original_get_scraper = main_module.get_scraper
        try:
            main_module.get_scraper = lambda platform, config: FakeScraper()
            process_url(
                url=content.url,
                config={"ai": {}},
                summarizer=None,
                exporters=[FakeExporter()],
                delay=0,
            )
        finally:
            main_module.get_scraper = original_get_scraper

        self.assertEqual(exported["content"].content_id, content.content_id)
        self.assertEqual(exported["summary"].analysis, content.content)


class DoctorSmokeTest(unittest.TestCase):
    def test_check_config_readiness_reports_core_missing_items(self):
        config = {
            "cookies": {"xiaohongshu": "./cookies/xhs_cookies.json"},
            "ai": {
                "provider": "deepseek",
                "deepseek": {"api_key": "sk-xxxxx"},
                "gemini": {"api_key": ""},
            },
            "export": {
                "target": "notion",
                "notion": {
                    "api_key": "ntn_xxxxx",
                    "database_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                },
            },
        }
        ok_items, missing_items = _check_config_readiness(config)
        self.assertTrue(any("Skill / Agent 架构" in item for item in ok_items))
        self.assertTrue(any("Cookie 文件" in item for item in missing_items))
        self.assertTrue(any("Notion 未配置完成" in item for item in missing_items))

    def test_check_config_readiness_accepts_realistic_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_path = Path(tmpdir) / "xhs_cookies.json"
            cookie_path.write_text("[]", encoding="utf-8")
            config = {
                "cookies": {"xiaohongshu": str(cookie_path)},
                "ai": {
                    "provider": "deepseek",
                    "deepseek": {"api_key": "sk-real-key"},
                    "gemini": {"api_key": "or-real-key"},
                },
                "export": {
                    "target": "notion",
                    "notion": {
                        "api_key": "ntn_real_key",
                        "database_id": "real_database_id",
                    },
                },
            }
            ok_items, missing_items = _check_config_readiness(config)
            self.assertTrue(any("Cookie 文件" in item for item in ok_items))
            self.assertTrue(any("AI 已配置" in item for item in ok_items))
            self.assertTrue(any("Notion 导出配置已填写" in item for item in ok_items))
            self.assertEqual(missing_items, [])


class ArtifactSmokeTest(unittest.TestCase):
    def test_write_and_read_artifact_bundle_without_image_download(self):
        content = ScrapedContent(
            platform="xiaohongshu",
            content_id="0123456789abcdef01234567",
            url="https://www.xiaohongshu.com/explore/0123456789abcdef01234567",
            title="测试标题",
            content="测试正文",
            author_name="测试作者",
            tags=["标签1", "标签2"],
            image_urls=["https://example.com/image.jpg"],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = write_artifact_bundle(content, tmpdir, download_images=False)
            self.assertTrue((bundle_dir / "content.json").exists())
            self.assertTrue((bundle_dir / "source.md").exists())
            restored_content, local_image_paths = read_artifact_bundle(bundle_dir)
            self.assertEqual(restored_content.content_id, content.content_id)
            self.assertEqual(restored_content.tags, content.tags)
            self.assertEqual(local_image_paths, [])


if __name__ == "__main__":
    unittest.main()
