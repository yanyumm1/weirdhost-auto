#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, time
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright, TimeoutError

CAPTCHA_EXTENSION_DIR = "./extensions/captcha-solver"  # 插件目录

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

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {level}: {msg}")

    def has_cookie_auth(self):
        return bool(self.remember_web_cookie)

    def has_email_auth(self):
        return bool(self.email and self.password)

    def login_with_cookies(self, context):
        try:
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
            return True
        except Exception as e:
            self.log(f"Cookie 登录失败: {e}", "ERROR")
            return False

    def wait_cf_plugin(self, page, server_id, timeout=30):
        """等待 CF Turnstile 由插件处理"""
        self.log(f"🛡️ 服务器 {server_id} 等待 CF Turnstile（插件）")
        for i in range(timeout):
            time.sleep(1)
            try:
                # Turnstile iframe出现时，插件会自动打勾
                cf_iframe = page.frame_locator('iframe[src*="turnstile"]')
                if not cf_iframe:
                    return True
            except:
                continue
        # 超时未通过
        screenshot_path = f"cf_failed_{server_id}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        self.log(f"❌ CF 未通过，已截图 {screenshot_path}")
        return False

    def renew_server(self, page, server_url):
        server_id = server_url.split('/')[-1]
        self.log(f"📦 处理服务器 {server_id}")

        try:
            page.goto(server_url, wait_until="networkidle", timeout=30000)
            time.sleep(5)

            # 查找续期按钮
            button = page.locator('button:has-text("시간추가"), button:has-text("시간 추가")').first
            if not button.is_visible():
                self.log(f"❌ 未找到续期按钮 {server_id}")
                return "no_renew_button"

            button.click(force=True)
            time.sleep(2)

            # 等待 CF 插件
            if not self.wait_cf_plugin(page, server_id):
                return "cf_failed"

            # 简单检查页面变化
            content = page.content()
            success_keywords = ["시간이 추가되었습니다", "success", "추가되었습니다"]
            for k in success_keywords:
                if k in content:
                    self.log(f"✅ 服务器 {server_id} 续期成功")
                    return "renew_success"

            self.log(f"⚠️ 服务器 {server_id} 续期结果未知")
            return "renew_unknown"

        except Exception as e:
            self.log(f"❌ 服务器 {server_id} 续期失败: {e}", "ERROR")
            return "renew_error"

    def run(self):
        if not self.server_list:
            self.log("❌ 未设置服务器URL列表", "ERROR")
            return []

        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    f'--disable-extensions-except={CAPTCHA_EXTENSION_DIR}',
                    f'--load-extension={CAPTCHA_EXTENSION_DIR}',
                    '--disable-blink-features=AutomationControlled',
                ],
                slow_mo=self.slow_mo
            )

            context = browser.new_context(viewport={'width':1920,'height':1080})
            page = context.new_page()
            page.set_default_timeout(120000)
            page.set_default_navigation_timeout(120000)

            # 登录
            if self.has_cookie_auth():
                self.login_with_cookies(context)
            else:
                self.log("❌ 没有 Cookie，未实现邮箱登录", "WARNING")

            for server_url in self.server_list:
                result = self.renew_server(page, server_url)
                self.server_results[server_url.split('/')[-1]] = result
                results.append(f"{server_url.split('/')[-1]}: {result}")
                time.sleep(5)

            browser.close()
        return results

def main():
    auto = WeirdhostAuto()
    results = auto.run()
    print("📊 运行结果:")
    for r in results:
        print(r)

if __name__ == "__main__":
    main()