#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright, TimeoutError


EXTENSION_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "extensions",
    "captcha-solver"
)


class WeirdhostAuto:
    def __init__(self):
        self.url = os.getenv('WEIRDHOST_URL', 'https://hub.weirdhost.xyz')
        self.server_urls = os.getenv('WEIRDHOST_SERVER_URLS', '')
        self.login_url = os.getenv('WEIRDHOST_LOGIN_URL', 'https://hub.weirdhost.xyz/auth/login')

        self.remember_web_cookie = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.email = os.getenv('WEIRDHOST_EMAIL', '')
        self.password = os.getenv('WEIRDHOST_PASSWORD', '')

        self.headless = os.getenv('HEADLESS', 'true').lower() == 'true'

        self.server_list = [u.strip() for u in self.server_urls.split(',') if u.strip()]
        self.server_results = {}

    def log(self, msg, level="INFO"):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {level}: {msg}")

    # ================= CF / Turnstile 插件处理 =================
    def wait_cf_turnstile_by_plugin(self, page, server_id):
        self.log(f"🛡️ 服务器 {server_id} 等待 CF Turnstile (插件模式)")

        try:
            page.wait_for_function(
                """
                () => Array.from(document.querySelectorAll("iframe"))
                    .some(f => f.src && f.src.includes("challenges.cloudflare.com"))
                """,
                timeout=60000
            )

            self.log(f"⚠️ 服务器 {server_id} Turnstile 已出现，等待插件")

            page.wait_for_function(
                """
                () => !Array.from(document.querySelectorAll("iframe"))
                    .some(f => f.src && f.src.includes("challenges.cloudflare.com"))
                """,
                timeout=120000
            )

            self.log(f"✅ 服务器 {server_id} CF 已通过（插件完成）")
            return True

        except TimeoutError:
            self.log(f"❌ 服务器 {server_id} CF 未通过", "ERROR")
            return False

    # ================= 登录 =================
    def login_with_cookie(self, context, page):
        self.log("🍪 使用 Cookie 登录")

        context.add_cookies([{
            "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
            "value": self.remember_web_cookie,
            "domain": "hub.weirdhost.xyz",
            "path": "/",
            "httpOnly": True,
            "secure": True,
        }])

        page.goto(self.url, timeout=60000)
        time.sleep(3)

        return "login" not in page.url.lower()

    # ================= 续期核心 =================
    def click_renew_button_and_check(self, page, button, server_id):
        try:
            self.log(f"🖱️ 点击续期按钮 ({server_id})")

            button.scroll_into_view_if_needed()
            button.click(force=True)

            # 👇 只在这里处理 CF
            self.wait_cf_turnstile_by_plugin(page, server_id)

            time.sleep(5)

            page_text = page.content().lower()

            success_keywords = [
                "시간이 추가",
                "추가되었습니다",
                "success",
                "added"
            ]

            already_keywords = [
                "이미",
                "already",
                "오늘은"
            ]

            for k in success_keywords:
                if k in page_text:
                    return "renew_success"

            for k in already_keywords:
                if k in page_text:
                    return "already_renewed"

            return "renew_unknown"

        except Exception as e:
            self.log(f"❌ 点击续期失败: {e}", "ERROR")
            return "renew_error"

    def renew_server(self, page, server_url):
        server_id = server_url.split('/')[-1]
        self.log(f"📦 开始处理服务器 {server_id}")

        page.goto(server_url, wait_until="networkidle", timeout=60000)
        time.sleep(5)

        button = page.locator('button:has-text("시간 추가")').first

        if not button or not button.is_visible():
            self.log(f"❌ 未找到续期按钮 {server_id}")
            return "no_renew_button"

        return self.click_renew_button_and_check(page, button, server_id)

    # ================= 主流程 =================
    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    f"--disable-extensions-except={EXTENSION_PATH}",
                    f"--load-extension={EXTENSION_PATH}",
                ],
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'
            )

            page = context.new_page()

            if not self.login_with_cookie(context, page):
                self.log("❌ Cookie 登录失败", "ERROR")
                return

            self.log("✅ 登录成功")

            for server_url in self.server_list:
                result = self.renew_server(page, server_url)
                self.server_results[server_url.split('/')[-1]] = result
                self.log(f"结果: {result}")
                time.sleep(10)

            browser.close()


def main():
    auto = WeirdhostAuto()
    auto.run()


if __name__ == "__main__":
    main()