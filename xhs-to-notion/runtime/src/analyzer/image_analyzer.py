import base64
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

from src.utils.logger import logger


IMAGE_ANALYSIS_PROMPT = """你是一个社交媒体内容分析助手。请分析这张小红书笔记图片的内容。

要求：
1. 提取图片中所有可见的文字内容
2. 描述图片的整体布局和视觉结构
3. 总结这张图片传达的核心信息
4. 如果是多张幻灯片之一，说明这张在整体内容中的角色

请用中文回复，简洁但完整。"""

BATCH_ANALYSIS_PROMPT = """你是一个社交媒体内容分析助手。以下是小红书笔记中全部 {total} 张图片的逐张分析。

请基于这些图片分析，给出一个整体总结：
1. 这个笔记的核心主题是什么？
2. 图片之间的逻辑关系（如：是什么类型的多图内容？幻灯片教程？产品展示？）
3. 综合所有图片，最关键的 3-5 个信息点是什么？

逐张分析结果：
{image_results}

请用中文回复，简洁但完整。"""


class ImageAnalyzer:

    def __init__(self, config: dict):
        gemini_cfg = config.get("ai", {}).get("gemini", {})
        api_key = gemini_cfg.get("api_key", "")
        self.model = gemini_cfg.get("model", "google/gemini-2.0-flash-001")
        base_url = gemini_cfg.get("base_url", "https://openrouter.ai/api/v1")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.max_workers = 4
        self.timeout = config.get("request", {}).get("timeout", 30)

    def analyze_images(self, image_urls: list[str]) -> str:
        if not image_urls:
            return ""

        logger.info(f"开始分析 {len(image_urls)} 张图片 (via OpenRouter: {self.model})...")

        # Download images in parallel
        images = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._download_image, url): i
                for i, url in enumerate(image_urls)
            }
            for future in as_completed(futures):
                i = futures[future]
                try:
                    images[i] = future.result(timeout=self.timeout)
                except Exception as e:
                    logger.warning(f"图片 [{i}] 下载失败: {e}")

        if not images:
            return "图片下载全部失败"

        # Analyze each image sequentially to avoid rate limits
        results = {}
        for i in sorted(images.keys()):
            try:
                logger.info(f"分析图片 [{i + 1}/{len(image_urls)}]...")
                results[i] = self._analyze_single(images[i], i)
            except Exception as e:
                logger.warning(f"图片 [{i}] 分析失败: {e}")
                results[i] = f"[图片 {i + 1} 分析失败]"

        # Build combined result
        parts = []
        for i in sorted(results.keys()):
            parts.append(f"--- 图片 {i + 1}/{len(image_urls)} ---\n{results[i]}")

        combined = "\n\n".join(parts)
        logger.info(f"图片分析完成: {len(results)}/{len(image_urls)} 张")

        # If multiple images, get a batch summary
        if len(results) >= 2:
            try:
                batch_summary = self._batch_summarize(len(image_urls), combined)
                return f"{batch_summary}\n\n=== 逐张详情 ===\n\n{combined}"
            except Exception as e:
                logger.warning(f"批量总结失败: {e}")

        return combined

    def _download_image(self, url: str) -> bytes:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.xiaohongshu.com/",
        }
        resp = requests.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.content

    def _analyze_single(self, image_bytes: bytes, index: int) -> str:
        data_uri = self._to_data_uri(image_bytes)
        prompt = f"[图片 {index + 1}] {IMAGE_ANALYSIS_PROMPT}"
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }],
        )
        return response.choices[0].message.content

    def _batch_summarize(self, total: int, image_results: str) -> str:
        prompt = BATCH_ANALYSIS_PROMPT.format(
            total=total, image_results=image_results
        )
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    @staticmethod
    def _to_data_uri(image_bytes: bytes) -> str:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"
