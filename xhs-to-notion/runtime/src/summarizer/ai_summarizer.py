from dataclasses import dataclass
from openai import OpenAI

from src.scrapers.base import ScrapedContent
from src.utils.logger import logger


@dataclass
class Summary:
    """AI 总结输出 — 只有 AI 自由发挥的分析文本"""
    analysis: str = ""


SUMMARY_PROMPT = """你是一位资深内容分析师。请深度分析以下{platform}内容，写一篇结构清晰的分析笔记。

要求：
- 先用一句话点破这条内容的核心价值
- 然后用你认为最合适的方式展开分析，不限制格式
- 要让读者看完你的分析就不需要再去看原内容
- 如果内容本身质量不高，直接说，不要美化

原始内容：
标题：{title}
作者：{author}

{content}

互动数据：{likes}赞 · {comments}评论 · {collects}收藏"""


class AISummarizer:

    def __init__(self, config: dict):
        ai = config["ai"]
        self.provider = ai.get("provider", "deepseek")
        provider_cfg = ai.get(self.provider, {})

        if self.provider in ("deepseek", "openai"):
            base_url = provider_cfg.get("base_url")
            if not base_url and self.provider == "deepseek":
                base_url = "https://api.deepseek.com"
            self.client = OpenAI(
                api_key=provider_cfg["api_key"],
                base_url=base_url,
            )
            self.model = provider_cfg.get("model", "deepseek-chat")
        else:
            raise ValueError(f"不支持的 AI provider: {self.provider}")

    def summarize(self, content: ScrapedContent, image_analysis: str = "") -> Summary:
        platform_name = "小红书" if content.platform == "xiaohongshu" else "抖音"

        full_content = content.content
        if image_analysis:
            full_content = (
                f"### 图片内容分析\n{image_analysis}\n\n"
                f"### 正文\n{content.content}"
            )

        prompt = SUMMARY_PROMPT.format(
            platform=platform_name,
            title=content.title,
            author=content.author_name,
            content=full_content[:8000],
            likes=content.like_count,
            comments=content.comment_count,
            collects=content.collect_count,
        )

        logger.info(f"调用 {self.provider} API 生成总结...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )

        analysis = response.choices[0].message.content.strip()
        return Summary(analysis=analysis)
