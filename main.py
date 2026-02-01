#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

CAPTCHA_EXTENSION_DIR = "./extensions/captcha-solver"


class WeirdhostAuto:
    def __init__(self):
        self.url = os.getenv('WEIRDHOST_URL', 'https://hub.weirdhost.xyz')
        self.server_urls = os.getenv('WEIRDHOST_SERVER_URLS', '')
        self.login_url = os.getenv('WEIRDHOST_LOGIN_URL', 'https://hub.weirdhost.xyz/auth/login')
        self.remember_web_cookie = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.headless = os.getenv('HEADLESS', 'true').lower() == 'true'
        self.slow_mo = int(os.getenv('SLOW_MO', '120'))
        self.server_list = [u.strip() for u in self.server_urls.split(',') if u.strip()]
        self.server_results = {}

    def log(self, msg, level="INFO"):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts}] {level}: {msg}")

    # -------------------------
    # 登录（Cookie）
    # -------------------------
    def login_with_cookies(self, context):
        self.log("🍪 使用 Cookie 登录")
        cookie = {
            'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
            'value': self.remember_web_cookie,
            'domain': 'hub.weirdhost.xyz',
            'path': '/',
            'expires': int(time.time()) + 3600 * 24 * 365,
            'httpOnly': True,
            'secure': True,
            'sameSite': 'Lax'
        }
        context.add_cookies([cookie])

    # -------------------------
    # 等 CF Turnstile 出现 → 消失
    # -------------------------
    def wait_cf_turnstile(self, page, server_id, timeout=60):
        self.log(f"🛡️ 服务器 {server_id} 等待 CF Turnstile")

        # 1️⃣ 等 iframe 出现（不一定每次都有）
        try:
            page.wait_for_selector(
                'iframe[src*="challenges.cloudflare.com"]',
                timeout=10000
            )
            self.log("🔍 检测到 CF Turnstile iframe")
        except TimeoutError:
            self.log("⚠️ 未检测到 CF iframe，可能未触发")
            return True

        # 2️⃣ 等 iframe 消失（插件完成）
        try:
            page.wait_for_selector(
                'iframe[src*="challenges.cloudflare.com"]',
                state='detached',
                timeout=timeout * 1000
            )
            self.log(f"✅ CF Turnstile 已通过 {server_id}")
            return True
        except TimeoutError:
            screenshot = f"cf_failed_{server_id}.png"
            page.screenshot(path=screenshot, full_page=True)
            self.log(f"❌ CF 未通过，已截图 {screenshot}", "ERROR")
            return False

    # -------------------------
    # 单服务器续期
    # -------------------------
    def renew_server(self, context, server_url):
        server_id = server_url.split('/')[-1]
        self.log(f"📦 处理服务器 {server_id}")

        page = context.new_page()
        page.set_default_timeout(120000)

        try:
            page.goto(server_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            button = page.locator(
                'button:has-text("시간추가"), button:has-text("시간 추가")'
            ).first

            if not button.is_visible():
                self.log(f"❌ 未找到续期按钮 {server_id}", "ERROR")
                return "no_renew_button"

            # 模拟人类操作
            button.hover()
            time.sleep(1)
            button.click()
            time.sleep(2)

            # 等 CF
            if not self.wait_cf_turnstile(page, server_id):
                return "cf_failed"

            # 判断结果
            html = page.content()
            success_keywords = [
                "시간이 추가되었습니다",
                "추가되었습니다",
                "success"
            ]

            if any(k in html for k in success_keywords):
                self.log(f"✅ 服务器 {server_id} 续期成功")
                return "renew_success"

            self.log(f"⚠️ 服务器 {server_id} 续期状态未知")
            return "renew_unknown"

        except Exception as e:
            self.log(f"❌ 服务器 {server_id} 异常: {e}", "ERROR")
            return "renew_error"

        finally:
            page.close()

    # -------------------------
    # 主流程
    # -------------------------
    def run(self):
        if not self.server_list:
            self.log("❌ 未设置服务器URL列表", "ERROR")
            return []

        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    f'--disable-extensions-except={CAPTCHA_EXTENSION_DIR}',
                    f'--load-extension={CAPTCHA_EXTENSION_DIR}',
                    '--disable-blink-features=AutomationControlled',
                ]
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='ko-KR',
                timezone_id='Asia/Seoul',
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            )

            # 注入 Cookie
            self.login_with_cookies(context)

            # 先访问首页“热身”
            page = context.new_page()
            page.goto(self.url, wait_until="domcontentloaded")
            time.sleep(3)
            page.close()

            # 逐个服务器处理（隔离页面）
            for server_url in self.server_list:
                result = self.renew_server(context, server_url)
                sid = server_url.split('/')[-1]
                self.server_results[sid] = result
                results.append(f"{sid}: {result}")
                time.sleep(10)

            browser.close()

        return results


def main():
    auto = WeirdhostAuto()
    results = auto.run()
    print("\n📊 运行结果:")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()