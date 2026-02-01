#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright, TimeoutError


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

    # ------------------------------------------------------------------
    # 通用日志
    # ------------------------------------------------------------------
    def log(self, msg, level="INFO"):
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {level}: {msg}")

    # ------------------------------------------------------------------
    # Cloudflare：点击后专用 Turnstile bypass（核心）
    # ------------------------------------------------------------------
    def handle_cf_after_click(self, page, server_id, timeout=90):
        self.log(f"🛡️ 服务器 {server_id} 进入点击后 CF 处理模式")

        start = time.time()
        indicators = [
            'iframe[src*="turnstile"]',
            'iframe[src*="challenges.cloudflare.com"]',
            '#challenge-form',
            '#challenge-stage',
            '#challenge-running',
            'text=Checking your browser',
            'text=Just a moment',
            'text=Verify'
        ]

        last = None
        while time.time() - start < timeout:
            detected = False
            for sel in indicators:
                try:
                    loc = page.locator(sel)
                    if loc.count() > 0 and loc.first.is_visible():
                        detected = True
                        if last != sel:
                            self.log(f"⚠️ CF 检测中: {sel}")
                            last = sel
                        break
                except:
                    pass

            if not detected:
                self.log(f"✅ 服务器 {server_id} CF / Turnstile 已通过")
                return True

            time.sleep(1.5)

        self.log(f"⚠️ 服务器 {server_id} CF 等待超时", "WARNING")
        return False

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------
    def login_with_cookie(self, context, page):
        if not self.remember_web_cookie:
            return False

        self.log("尝试 Cookie 登录")
        context.add_cookies([{
            'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
            'value': self.remember_web_cookie,
            'domain': 'hub.weirdhost.xyz',
            'path': '/',
            'httpOnly': True,
            'secure': True,
            'sameSite': 'Lax'
        }])

        page.goto(self.url, wait_until="domcontentloaded")
        time.sleep(3)

        if "login" not in page.url:
            self.log("✅ Cookie 登录成功")
            return True

        self.log("Cookie 登录失败", "WARNING")
        return False

    def login_with_email(self, page):
        self.log("尝试邮箱密码登录")
        page.goto(self.login_url, wait_until="domcontentloaded")

        page.fill('input[name="username"]', self.email)
        page.fill('input[name="password"]', self.password)

        with page.expect_navigation(timeout=90000):
            page.click('button[type="submit"]')

        if "login" in page.url:
            self.log("❌ 邮箱登录失败", "ERROR")
            return False

        self.log("✅ 邮箱登录成功")
        return True

    # ------------------------------------------------------------------
    # 查找「시간 추가」按钮
    # ------------------------------------------------------------------
    def find_renew_button(self, page):
        selectors = [
            'button:has-text("시간 추가")',
            'button:has-text("시간추가")',
            '//button[contains(text(),"시간")]'
        ]
        for sel in selectors:
            try:
                btn = page.locator(f'xpath={sel}' if sel.startswith('//') else sel)
                btn.wait_for(state='visible', timeout=8000)
                if btn.is_enabled():
                    return btn
            except:
                pass
        return None

    # ------------------------------------------------------------------
    # 点击续期 + CF 处理 + 成功判断
    # ------------------------------------------------------------------
    def click_and_renew(self, page, button, server_id):
        self.log(f"🖱️ 点击续期按钮 ({server_id})")

        button.hover()
        time.sleep(1)
        button.click(force=True)

        # ⭐ 核心：点击后 CF
        self.handle_cf_after_click(page, server_id)

        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except:
            pass

        time.sleep(2)

        text = page.content().lower()

        success_keywords = [
            "시간이 추가",
            "추가되었습니다",
            "success",
            "added"
        ]

        already_keywords = [
            "이미",
            "already",
            "only once",
            "오늘은"
        ]

        if any(k in text for k in success_keywords):
            self.log(f"✅ 服务器 {server_id} 续期成功")
            return "renew_success"

        if any(k in text for k in already_keywords):
            self.log(f"ℹ️ 服务器 {server_id} 今日已续期")
            return "already_renewed"

        # 兜底：按钮是否被禁用
        try:
            after_btn = self.find_renew_button(page)
            if after_btn and not after_btn.is_enabled():
                self.log(f"✅ 按钮已禁用，判定成功")
                return "renew_success"
        except:
            pass

        self.log(f"⚠️ 服务器 {server_id} 结果不明确")
        return "renew_unknown"

    # ------------------------------------------------------------------
    # 单服务器处理
    # ------------------------------------------------------------------
    def process_server(self, page, server_url):
        server_id = server_url.rstrip('/').split('/')[-1]
        self.log(f"📦 处理服务器 {server_id}")

        page.goto(server_url, wait_until="networkidle")
        time.sleep(4)

        button = self.find_renew_button(page)
        if not button:
            self.log("❌ 未找到续期按钮")
            return "no_renew_button"

        return self.click_and_renew(page, button, server_id)

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox'
                ]
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale="ko-KR",
                timezone_id="Asia/Seoul"
            )

            page = context.new_page()
            page.set_default_timeout(120000)

            logged_in = False
            if self.remember_web_cookie:
                logged_in = self.login_with_cookie(context, page)

            if not logged_in and self.email:
                logged_in = self.login_with_email(page)

            if not logged_in:
                self.log("❌ 登录失败，终止", "ERROR")
                sys.exit(1)

            for url in self.server_list:
                result = self.process_server(page, url)
                self.log(f"结果: {result}")
                time.sleep(6)

            browser.close()


def main():
    print("🚀 Weirdhost 自动续期脚本启动")
    auto = WeirdhostAuto()
    auto.run()
    print("🎉 执行完成")


if __name__ == "__main__":
    main()