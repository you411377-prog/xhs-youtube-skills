import json
import requests
from src.utils.logger import logger


class CookieManager:

    @staticmethod
    def load(cookie_path: str) -> dict:
        with open(cookie_path, "r") as f:
            cookie_list = json.load(f)
        return {c["name"]: c["value"] for c in cookie_list}

    @staticmethod
    def check_douyin(cookies: dict) -> bool:
        url = "https://www.douyin.com/aweme/v1/web/user/profile/self/"
        try:
            s = requests.Session()
            s.cookies.update(cookies)
            resp = s.get(url, timeout=10)
            data = resp.json()
            return data.get("status_code") == 0
        except Exception:
            return False

    @staticmethod
    def check_xiaohongshu(cookies: dict) -> bool:
        url = "https://edith.xiaohongshu.com/api/sns/web/v1/user/selfinfo"
        try:
            s = requests.Session()
            s.cookies.update(cookies)
            resp = s.get(url, timeout=10)
            data = resp.json()
            return data.get("success", False)
        except Exception:
            return False
