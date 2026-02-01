#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

CAPTCHA_EXTENSION_DIR = "./extensions/captcha-solver"

# -----------------------------
# 日志函数
# -----------------------------
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {level}: {msg}")

# -----------------------------
# 自动续期类
# -----------------------------
class WeirdhostAutoAPI:
    def __init__(self):
        self.server_urls = [u.strip() for u in os.getenv("WEIRDHOST_SERVER_URLS", "").split(",") if u.strip()]
        self.remember_web_cookie = os.getenv("REMEMBER_WEB_COOKIE", "")
        self.headless = os.getenv("HEADLESS", "true").lower() == "true"
        self.slow_mo = int(os.getenv("SLOW_MO", "150"))

    # 登录 Cookie
    def login_with_cookies(self, context):
        context.add_cookies([{
            "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
            "value": self.remember_web_cookie,
            "domain": "hub.weirdhost.xyz",
            "path": "/",
            "expires": int(time.time()) + 3600*24*365,
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax"
        }])
        log("🍪 使用 Cookie 登录")

    # 单服务器续期
    def renew_server(self, context, server_url):
        server_id = server_url.split("/")[-1]
        log(f"📦 处理服务器 {server_id}")

        page = context.new_page()
        page.set_default_timeout(120000)

        cf_token = None

        # 监听网络请求抓 cf-turnstile-response
        def on_request(req):
            nonlocal cf_token
            if "/renew" in req.url and req.method == "POST":
                try:
                    payload = req.post_data_json()
                    if payload and "cf-turnstile-response" in payload:
                        cf_token = payload["cf-turnstile-response"]
                except:
                    pass

        page.on("request", on_request)

        try:
            page.goto(server_url, wait_until="domcontentloaded")
            time.sleep(3)

            # 找到续期按钮
            button = page.locator('button:has-text("시간추가"), button:has-text("시간 추가")').first
            if button.count() == 0 or not button.is_visible():
                log(f"❌ 未找到续期按钮", "ERROR")
                return "no_renew_button"

            button.scroll_into_view_if_needed()
            time.sleep(0.5)

            # 点击按钮触发 CF + Ajax
            button.click(force=True)
            log(f"🛡️ 服务器 {server_id} 点击续期按钮，等待 CF Turnstile 自动完成...")

            # 等待 Ajax 发出，最多 30 秒
            for _ in range(30):
                if cf_token:
                    break
                time.sleep(1)

            if not cf_token:
                log("❌ 未抓到 cf-turnstile-response", "ERROR")
                return "cf_failed"

            log(f"✅ 服务器 {server_id} 获取 cf-turnstile-response 成功")

            # 直接用 requests POST API
            api_url = f"https://hub.weirdhost.xyz/api/client/freeservers/a79a2b26-ad80- 45c3-a25d-42alceed3aba/renew"
            cookies = {
                "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d": self.remember_web_cookie
            }
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            payload = {"cf-turnstile-response": cf_token}

            resp = requests.post(api_url, cookies=cookies, headers=headers, json=payload, timeout=30)
            log(f"📡 Renew API status: {resp.status_code} / body: {resp.text}")

            # 判定状态
            if resp.status_code == 200:
                body = resp.json()
                if body.get("success") or "true" in str(body).lower():
                    return "renew_success"
                if "cooldown" in str(body).lower():
                    return "cooldown"
                if "unauthorized" in str(body).lower():
                    return "unauthorized"
            if resp.status_code in (403, 429):
                return "blocked"
            return "renew_failed"

        except Exception as e:
            log(f"❌ 服务器 {server_id} 异常: {e}", "ERROR")
            return "renew_error"
        finally:
            page.close()

    # 主流程
    def run(self):
        if not self.server_urls:
            log("❌ 未设置服务器URL", "ERROR")
            return {}

        results = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    f"--disable-extensions-except={CAPTCHA_EXTENSION_DIR}",
                    f"--load-extension={CAPTCHA_EXTENSION_DIR}",
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            context = browser.new_context(
                viewport={"width":1920,"height":1080},
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            )

            self.login_with_cookies(context)

            for server_url in self.server_urls:
                sid = server_url.split("/")[-1]
                result = self.renew_server(context, server_url)
                results[sid] = result
                time.sleep(5)

            browser.close()

        return results

# -----------------------------
# 主入口
# -----------------------------
def main():
    auto = WeirdhostAutoAPI()
    results = auto.run()
    print("\n📊 运行结果 JSON:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()