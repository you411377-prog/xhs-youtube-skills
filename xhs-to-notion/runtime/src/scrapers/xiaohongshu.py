import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from src.scrapers.base import BaseScraper, ScrapedContent
from src.utils.logger import logger


class XiaohongshuScraper(BaseScraper):

    BASE_URL = "https://www.xiaohongshu.com/explore/{note_id}"

    # Multi-selector fallbacks — updated for current XHS DOM (2026.05)
    SELECTORS = {
        "title": [
            "#detail-title", "[class*='title']", "h1",
            "[class*='note'] [class*='title']",
        ],
        "desc": [
            "#detail-desc", "[class*='desc']", "[class*='note-text']",
            "[class*='content'] [class*='text']",
        ],
        "author": [
            "[class*='username']", "[class*='author']", "[class*='name']",
            "a[href*='/user/']",
        ],
        "like": [
            "[class*='like'] [class*='count']", "[class*='like-count']",
            "[class*='liked']", "[class*='interact'] [class*='count']",
        ],
        "tags": ["[class*='tag']", "[class*='topic']", "a[href*='/topic/']"],
        "images": [
            "[class*='note'] img", "[class*='swiper'] img",
            "[class*='carousel'] img",
        ],
        "publish_time": [
            "[class*='date']", "[class*='time']", "[class*='bottom'] span",
        ],
        "interact_bar": [
            "[class*='interact']", "[class*='action']", "[class*='bottom']",
        ],
    }

    # Only detect actual login modals, not general masks
    LOGIN_SELECTORS = [
        "[class*='login-modal']", "[class*='login-container']",
        "[class*='LoginPage']",
    ]
    COMMENT_SKIP_WORDS = {
        "置顶评论", "回复", "赞", "说点什么...", "发送", "取消", "举报",
        "更多评论", "作者", "共", "条评论", "鼠标悬停查看", "可以添加到收藏夹啦",
    }

    def __init__(self, cookie_path: str, config: dict):
        super().__init__(cookie_path, config)
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        logger.info("小红书采集器: Playwright 浏览器已启动")

    def close(self):
        self._browser.close()
        self._playwright.stop()
        logger.info("小红书采集器: Playwright 浏览器已关闭")

    def _create_context(self):
        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        # Anti-detection: hide webdriver
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            window.chrome = { runtime: {} };
        """)
        # Inject cookies
        cookie_list = []
        for name, value in self.cookies.items():
            cookie_list.append({
                "name": name, "value": value,
                "domain": ".xiaohongshu.com", "path": "/",
            })
        context.add_cookies(cookie_list)
        return context

    def _detect_login_wall(self, page) -> bool:
        """Check if content requires login — use specific selectors only."""
        for selector in self.LOGIN_SELECTORS:
            el = page.query_selector(selector)
            if el and el.is_visible():
                return True
        # Also check body text for login-only keywords
        body = page.inner_text("body")
        if "手机号登录" in body and "验证码登录" in body:
            return True
        return False

    def _safe_text(self, page, selectors: list[str]) -> str:
        for sel in selectors:
            try:
                els = page.query_selector_all(sel)
                for el in els:
                    text = el.inner_text().strip()
                    # Filter out nav/footer noise
                    if text and len(text) > 1 and text not in (
                        "发现", "直播", "发布", "通知", "我",
                        "创作中心", "业务合作", "推荐", "穿搭", "美食",
                        "彩妆", "影视", "职场", "情感", "家居", "游戏",
                        "旅行", "健身",
                    ):
                        return text
            except Exception:
                continue
        return ""

    def _safe_count(self, page, selectors: list[str]) -> int:
        text = self._safe_text(page, selectors)
        if not text:
            return 0
        text = text.replace(",", "").strip()
        if "万" in text:
            try:
                return int(float(text.replace("万", "")) * 10000)
            except ValueError:
                pass
        try:
            return int(re.sub(r"[^\d]", "", text)) if re.search(r"\d", text) else 0
        except ValueError:
            return 0

    def _extract_publish_time(self, page) -> datetime | None:
        text = self._safe_text(page, self.SELECTORS["publish_time"])
        if not text:
            return None
        now = datetime.now()
        m = re.search(r"(\d+)\s*分钟前", text)
        if m:
            return now - timedelta(minutes=int(m.group(1)))
        m = re.search(r"(\d+)\s*小时前", text)
        if m:
            return now - timedelta(hours=int(m.group(1)))
        m = re.search(r"(\d+)\s*天前", text)
        if m:
            return now - timedelta(days=int(m.group(1)))
        m = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})", text)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        return None

    def _extract_author_from_body(self, body: str) -> tuple[str, str]:
        """Try to extract author info from body text patterns."""
        # Pattern: "AuthorName\n互动数据" or similar
        # Look for common patterns after the title
        lines = [l.strip() for l in body.split("\n") if l.strip()]
        # Filter out known nav/footer lines
        nav_words = {
            "发现", "直播", "发布", "通知", "我", "创作中心", "业务合作",
            "推荐", "穿搭", "美食", "彩妆", "影视", "职场", "情感", "家居",
            "游戏", "旅行", "健身", "沪ICP备", "营业执照", "©",
        }
        content_lines = [l for l in lines if not any(w in l for w in nav_words)]
        return "", ""

    def _looks_like_comment_meta(self, text: str) -> bool:
        return bool(
            re.match(r"^\d+\s*(分钟前|小时前|天前)", text)
            or re.match(r"^\d{2}-\d{2}", text)
            or text in {"江苏", "上海", "北京", "广东", "云南", "马来西亚"}
        )

    def _extract_top_comments(self, content_lines: list[str], author: str) -> list[dict]:
        comments: list[dict] = []
        start_idx = -1
        for i, line in enumerate(content_lines):
            if re.match(r"共\s*\d+\s*条评论", line):
                start_idx = i + 1
                break
        if start_idx == -1:
            return comments

        i = start_idx
        while i < len(content_lines) and len(comments) < 5:
            line = content_lines[i].strip()
            if (
                not line
                or line == author
                or any(word in line for word in self.COMMENT_SKIP_WORDS)
                or self._looks_like_comment_meta(line)
                or re.match(r"^\d+$", line)
            ):
                i += 1
                continue

            commenter = line
            comment_text = ""
            if i + 1 < len(content_lines):
                next_line = content_lines[i + 1].strip()
                if (
                    next_line
                    and not any(word in next_line for word in self.COMMENT_SKIP_WORDS)
                    and not re.match(r"^\d+$", next_line)
                    and not self._looks_like_comment_meta(next_line)
                ):
                    comment_text = next_line
                    i += 2
                else:
                    i += 1
            else:
                i += 1

            if commenter and comment_text:
                comments.append({
                    "author": commenter[:100],
                    "content": comment_text[:500],
                })

        return comments

    def fetch(self, content_id: str, xsec_token: str = "",
              xsec_source: str = "") -> ScrapedContent:
        url = self.BASE_URL.format(note_id=content_id)
        if xsec_token:
            url += f"?xsec_token={xsec_token}"
            if xsec_source:
                url += f"&xsec_source={xsec_source}"
        context = self._create_context()
        page = context.new_page()

        try:
            logger.info(f"正在采集小红书笔记: {content_id}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Check if redirected (e.g., to /explore homepage = note inaccessible)
            if content_id not in page.url:
                raise RuntimeError(
                    f"笔记被重定向到首页，可能已被删除、设为私密或不支持直接访问。"
                    f"请确保分享链接中包含 xsec_token 参数: {url}"
                )

            # Wait for content to render
            page.wait_for_timeout(3000)

            # Check for login wall
            if self._detect_login_wall(page):
                raise RuntimeError(
                    "小红书需要登录，Cookie 可能已过期。"
                    "请重新导出 Cookie 并保存到 cookies/xhs_cookies.json"
                )

            # Scroll to trigger lazy loading
            page.evaluate("window.scrollTo(0, 300)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # Extract page title (XHS format: "Title - 小红书")
            page_title = page.title()
            title = page_title.replace(" - 小红书", "").strip() if " - 小红书" in page_title else ""

            # Extract body text and parse structured content
            body = page.inner_text("body")
            lines = [l.strip() for l in body.split("\n") if l.strip()]

            # Filter out navigation/footer noise
            nav_words = {
                "发现", "直播", "发布", "通知", "我", "创作中心", "业务合作",
                "推荐", "穿搭", "美食", "彩妆", "影视", "职场", "情感", "家居",
                "游戏", "旅行", "健身", "沪ICP备", "营业执照", "©", "活动",
                "更多", "地址：", "电话：", "行吟信息科技",
            }
            content_lines = [
                l for l in lines
                if not any(w in l for w in nav_words) and not l.startswith("http")
            ]

            # Find author — line near "关注"
            author = ""
            follow_idx = -1
            for i, l in enumerate(content_lines):
                if l == "关注" and i > 0 and not content_lines[i - 1].isdigit():
                    author = content_lines[i - 1]
                    follow_idx = i
                    break
            if not author:
                # Try CSS selectors for author
                author = self._safe_text(page, self.SELECTORS["author"])

            # Find title if not from page title
            if not title:
                title = self._safe_text(page, self.SELECTORS["title"])

            # Find description — text after title, before tags/date
            desc = ""
            tags = []
            date_str = ""
            comment_count = 0

            # Collect tags from # prefixed words
            import re as re_module
            tag_idx = -1
            for i, l in enumerate(content_lines):
                # Extract tags
                hashtags = re_module.findall(r"#(\S+)", l)
                for t in hashtags:
                    t = t.rstrip("#")
                    if t and len(t) < 30 and t not in tags:
                        tags.append(t)

                # Check for date pattern
                if re_module.match(r"\d{2}-\d{2}", l):
                    date_str = l
                    continue

                # Check for comment count
                cm = re_module.match(r"共\s*(\d+)\s*条评论", l)
                if cm:
                    comment_count = int(cm.group(1))
                    continue

            # Build desc from the content lines (skip header/footer stuff)
            skip_words = nav_words | {
                "关注", "作者", "置顶评论", "回复", "赞", "说点什么...",
                "发送", "取消", "- THE END -", "可以添加到收藏夹啦",
                "鼠标悬停查看", "举报", "评", "更多评论",
            }
            desc_parts = []
            in_content = False
            for l in content_lines:
                if l == author and not in_content:
                    continue
                if l == "关注" and not in_content:
                    in_content = True
                    continue
                if in_content:
                    if any(w in l for w in skip_words) or l.isdigit():
                        if l.isdigit() and len(l) <= 2:
                            continue
                        # Tags line is fine
                        if re_module.search(r"#\S", l):
                            desc_parts.append(l)
                            continue
                        # Date/comments line - stop
                        if re_module.match(r"\d{2}-\d{2}", l) or "条评论" in l:
                            break
                        # Author repeated = comment section starts
                        if l == author:
                            break
                        continue
                    desc_parts.append(l)

            desc = "\n".join(desc_parts) if desc_parts else ""
            if not desc:
                # Try CSS selectors for desc
                desc = self._safe_text(page, self.SELECTORS["desc"])

            # Extract title from first line of desc if not found yet
            if not title and desc_parts:
                title = desc_parts[0]

            # Clean up desc: remove title prefix, date suffix, inline tags
            if title and desc.startswith(title):
                desc = desc[len(title):].strip()
            # Remove date line at the end (e.g., "04-19 广东")
            desc = re.sub(r"\n?\d{2}-\d{2}\s*\S*$", "", desc).strip()
            # Remove inline hashtags at the end
            desc = re.sub(r"\n?\s*(?:#\S+\s*)+\s*$", "", desc).strip()

            # Extract images
            image_urls = []
            for img in page.query_selector_all("img"):
                src = img.get_attribute("src") or ""
                if "xhscdn.com" in src and "avatar" not in src and src not in image_urls:
                    image_urls.append(src)

            # Determine content type
            content_type = "image_text"
            if page.query_selector("video"):
                content_type = "video"
            # Slide counter like "1/8" indicates multi-image
            for l in content_lines:
                if re.match(r"\d+/\d+$", l):
                    content_type = "image_text"
                    break

            # Extract publish time from date_str
            publish_time = None
            if date_str:
                parts = date_str.split()
                date_part = parts[0] if parts else date_str
                try:
                    m = re.match(r"(\d{2})-(\d{2})", date_part)
                    if m:
                        now = datetime.now()
                        publish_time = datetime(now.year, int(m.group(1)), int(m.group(2)))
                except (ValueError, IndexError):
                    pass

            top_comments = self._extract_top_comments(content_lines, author)

            # Try to find like/collect counts
            like_count = 0
            collect_count = 0
            # Look for small numbers after the "发送 取消" area
            for i, l in enumerate(content_lines):
                if l == "发送":
                    # Numbers before and after may be interaction counts
                    if i > 0 and content_lines[i - 1].isdigit():
                        collect_count = int(content_lines[i - 1])
                    if i > 1 and content_lines[i - 2].isdigit():
                        like_count = int(content_lines[i - 2])
                    break

            if not title:
                title = "(无标题)"

            logger.info(
                f"小红书采集完成: {title[:40]} | 作者 {author} | "
                f"图片 {len(image_urls)} | 标签 {len(tags)}"
            )

            content = ScrapedContent(
                platform="xiaohongshu",
                content_id=content_id,
                url=url,
                title=title,
                content=desc or "",
                content_type=content_type,
                author_name=author or "未知作者",
                author_id="",
                publish_time=publish_time,
                like_count=like_count,
                comment_count=comment_count,
                share_count=0,
                collect_count=collect_count,
                tags=tags,
                image_urls=image_urls,
                extra={"top_comments": top_comments},
            )

            return content

        except PlaywrightTimeout:
            raise RuntimeError(
                f"小红书页面加载超时: {url}。笔记可能已被删除或设为私密。"
            )
        finally:
            context.close()
