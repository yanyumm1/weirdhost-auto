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
        self.slow_mo = int(os.getenv('SLOW_MO', '100'))
        self.server_list = [url.strip() for url in self.server_urls.split(',') if url.strip()]
        self.server_results = {}

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {level}: {message}")

    # --- 登录 ---
    def has_cookie_auth(self):
        return bool(self.remember_web_cookie)

    def has_email_auth(self):
        return bool(self.email and self.password)

    def check_login_status(self, page):
        try:
            if "login" in page.url or "auth" in page.url:
                self.log("当前在登录页面，未登录")
                return False
            return True
        except:
            return False

    def login_with_cookies(self, context):
        try:
            self.log("尝试使用 Cookies 登录...")
            session_cookie = {
                'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                'value': self.remember_web_cookie,
                'domain': 'hub.weirdhost.xyz',
                'path': '/',
                'expires': int(time.time()) + 3600 * 24 * 365,
                'httpOnly': True,
                'secure': True,
                'sameSite': 'Lax'
            }
            context.add_cookies([session_cookie])
            self.log("已添加 remember_web cookie")
            return True
        except Exception as e:
            self.log(f"设置 Cookies 时出错: {e}", "ERROR")
            return False

    def login_with_email(self, page):
        try:
            self.log("尝试邮箱密码登录...")
            page.goto(self.login_url, wait_until="domcontentloaded")
            page.fill('input[name="username"]', self.email)
            page.fill('input[name="password"]', self.password)
            with page.expect_navigation(wait_until="domcontentloaded", timeout=90000):
                page.click('button[type="submit"]')
            return self.check_login_status(page)
        except Exception as e:
            self.log(f"邮箱密码登录出错: {e}", "ERROR")
            return False

    # --- CF处理 (点击后盾) ---
    def handle_cf_challenge(self, page, server_id):
        try:
            cf_selectors = ['#challenge-form', '.challenge-form', '#cf-content', 'text=Checking your browser']
            for selector in cf_selectors:
                try:
                    if page.locator(selector).is_visible(timeout=3000):
                        self.log(f"⚠️ 服务器 {server_id} CF / Turnstile 触发，等待通过...")
                        time.sleep(10)
                        if page.locator(selector).is_visible(timeout=3000):
                            self.log(f"⚠️ 服务器 {server_id} CF仍然存在，继续等待5秒")
                            time.sleep(5)
                        self.log(f"✅ 服务器 {server_id} CF / Turnstile 已通过")
                        return True
                except:
                    continue
            return False
        except Exception as e:
            self.log(f"CF检查失败: {e}", "WARNING")
            return False

    # --- 查找续期按钮 ---
    def find_renew_button(self, page, server_id):
        selectors = [
            'button:has-text("시간추가")',
            'button:has-text("시간 추가")',
        ]
        for selector in selectors:
            try:
                button = page.locator(selector)
                button.wait_for(state='visible', timeout=5000)
                if button.is_visible():
                    self.log(f"✅ 服务器 {server_id} 找到续期按钮: {selector}")
                    return button
            except:
                continue
        return None

    # --- 点击续期并处理 CF盾 ---
    def click_renew_button_and_check(self, page, button, server_id):
        try:
            before_url = page.url
            main_content = page.locator('main, .container, .content').first
            before_content = main_content.text_content()[:500] if main_content.count() > 0 else ""

            self.log(f"🖱️ 点击续期按钮 ({server_id})")
            button.hover()
            time.sleep(1)
            button.click(force=True)

            # 点击后 CF / Turnstile
            self.handle_cf_challenge(page, server_id)

            time.sleep(3)  # 等待页面刷新
            screenshot_path = f"screenshots/{server_id}_{int(time.time())}.png"
            os.makedirs('screenshots', exist_ok=True)
            page.screenshot(path=screenshot_path, full_page=True)
            self.log(f"📸 已保存点击后截图: {screenshot_path}")

            # 判断结果
            after_content = main_content.text_content()[:500] if main_content.count() > 0 else ""
            page_text = page.content().lower()

            success_keywords = ["시간이 추가되었습니다", "추가되었습니다", "성공", "success", "added"]
            already_keywords = ["이미 추가", "already", "한번만", "오늘은 더 이상"]

            for keyword in success_keywords:
                if keyword in page_text:
                    self.log(f"✅ 服务器 {server_id} 续期成功")
                    return "renew_success"
            for keyword in already_keywords:
                if keyword in page_text:
                    self.log(f"ℹ️ 服务器 {server_id} 已续期过")
                    return "already_renewed"

            if before_content != after_content:
                self.log(f"⚠️ 服务器 {server_id} 内容已变化，但未明确成功")
                return "renew_content_changed"

            return "renew_no_change"
        except Exception as e:
            self.log(f"点击续期出错: {e}", "ERROR")
            return "renew_click_error"

    # --- 执行续期流程 ---
    def renew_server(self, page, server_url):
        server_id = server_url.split('/')[-1]
        page.goto(server_url, wait_until="networkidle")
        time.sleep(3)
        button = self.find_renew_button(page, server_id)
        if not button:
            self.log(f"❌ 服务器 {server_id} 未找到续期按钮")
            return "no_renew_button"
        return self.click_renew_button_and_check(page, button, server_id)

    # --- 处理单个服务器 ---
    def process_server(self, page, server_url):
        server_id = server_url.split('/')[-1] if server_url else "unknown"
        self.log(f"📦 处理服务器 {server_id}")
        self.server_results[server_id] = {'renew_status': '未执行'}

        renewal_status = self.renew_server(page, server_url)
        self.server_results[server_id]['renew_status'] = renewal_status

        return f"{server_id}: {renewal_status}"

    # --- 主流程 ---
    def run(self):
        results = []
        if not self.has_cookie_auth() and not self.has_email_auth():
            self.log("❌ 无可用认证信息", "ERROR")
            return ["error: no_auth"]
        if not self.server_list:
            self.log("❌ 未设置服务器列表", "ERROR")
            return ["error: no_servers"]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            login_success = False

            if self.has_cookie_auth() and self.login_with_cookies(context):
                page.goto(self.url)
                if self.check_login_status(page):
                    login_success = True

            if not login_success and self.has_email_auth():
                login_success = self.login_with_email(page)

            if not login_success:
                self.log("❌ 登录失败", "ERROR")
                return ["login_failed"] * len(self.server_list)

            for server_url in self.server_list:
                result = self.process_server(page, server_url)
                results.append(result)
                time.sleep(3)
        return results


def main():
    auto = WeirdhostAuto()
    results = auto.run()
    auto.log("🎉 执行完成")
    for server_id, status in auto.server_results.items():
        auto.log(f"服务器 {server_id} 状态: {status['renew_status']}")


if __name__ == "__main__":
    main()