#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

CAPTCHA_EXTENSION_DIR = "./extensions/captcha-solver"


class WeirdhostAuto:
    def __init__(self):
        self.url = os.getenv("WEIRDHOST_URL", "https://hub.weirdhost.xyz")
        self.server_urls = os.getenv("WEIRDHOST_SERVER_URLS", "")
        self.remember_web_cookie = os.getenv("REMEMBER_WEB_COOKIE", "")
        self.headless = os.getenv("HEADLESS", "true").lower() == "true"
        self.slow_mo = int(os.getenv("SLOW_MO", "150"))
        self.server_list = [u.strip() for u in self.server_urls.split(",") if u.strip()]

    def log(self, msg, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {level}: {msg}")

    # -----------------------------
    # Cookie 登录
    # -----------------------------
    def login_with_cookies(self, context):
        self.log("🍪 使用 Cookie 登录")
        context.add_cookies([{
            "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
            "value": self.remember_web_cookie,
            "domain": "hub.weirdhost.xyz",
            "path": "/",
            "expires": int(time.time()) + 3600 * 24 * 365,
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax"
        }])

    # -----------------------------
    # 等待 CF Turnstile 自动完成（插件处理）
    # -----------------------------
    def wait_cf_turnstile(self, page, server_id, timeout=30):
        self.log(f"🛡️ 服务器 {server_id} 等待 CF Turnstile（插件）")
        iframe_selector = 'iframe[src*="turnstile"]'
        start = time.time()
        while time.time() - start < timeout:
            try:
                if page.locator(iframe_selector).count() == 0:
                    # iframe 消失，CF 已完成
                    self.log(f"✅ 服务器 {server_id} CF 已完成")
                    return True
            except:
                pass
            time.sleep(1)
        # 超时未完成
        screenshot_path = f"cf_failed_{server_id}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        self.log(f"❌ CF 超时未完成，已截图 {screenshot_path}", "ERROR")
        return False

    # -----------------------------
    # 单服务器续期
    # -----------------------------
    def renew_server(self, context, server_url):
        server_id = server_url.split("/")[-1]
        self.log(f"📦 处理服务器 {server_id}")

        page = context.new_page()
        page.set_default_timeout(120000)

        renew_api = {"status": None, "url": None, "body": None}

        # -------- Network 监听 --------
        def on_response(resp):
            url = resp.url
            if "/renew" in url:
                try:
                    renew_api["status"] = resp.status
                    renew_api["url"] = url
                    renew_api["body"] = resp.text()
                except:
                    pass

        page.on("response", on_response)

        try:
            page.goto(server_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            # 找到续期按钮
            button = page.locator(
                'button:has-text("시간추가"), button:has-text("시간 추가")'
            ).first

            if button.count() == 0 or not button.is_visible():
                self.log("❌ 未找到续期按钮", "ERROR")
                return "no_renew_button"

            # ---------------- 点击按钮（触发 Ajax + CF Turnstile） ----------------
            button.scroll_into_view_if_needed()
            time.sleep(0.5)
            button.click(force=True)

            # 等待 CF Turnstile 完成
            if not self.wait_cf_turnstile(page, server_id):
                return "cf_failed"

            # 等 Ajax 请求完成
            time.sleep(5)

            # -------- Network 裁决 --------
            if renew_api["status"] is None:
                self.log("❌ 未捕获到续期 API 请求", "ERROR")
                return "no_api_request"

            self.log(f"📡 Renew API URL: {renew_api['url']}")
            self.log(f"📡 Renew API status: {renew_api['status']}")
            self.log(f"📡 Renew API response: {renew_api['body']}")

            body = renew_api["body"] or ""

            if renew_api["status"] == 200:
                if "success" in body or "true" in body:
                    self.log(f"✅ 服务器 {server_id} 续期成功")
                    return "renew_success"
                if "cooldown" in body:
                    self.log("⏳ 服务器处于冷却时间", "WARNING")
                    return "cooldown"
                if "unauthorized" in body:
                    self.log("🔒 Cookie 已失效", "ERROR")
                    return "unauthorized"

            if renew_api["status"] in (403, 429):
                self.log("🚫 被后端风控拦截", "ERROR")
                return "blocked"

            self.log("❌ 后端返回失败", "ERROR")
            return "renew_failed"

        except Exception as e:
            self.log(f"❌ 异常: {e}", "ERROR")
            return "renew_error"

        finally:
            page.close()

    # -----------------------------
    # 主流程
    # -----------------------------
    def run(self):
        if not self.server_list:
            self.log("❌ 未设置服务器URL", "ERROR")
            return []

        results = []

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
                viewport={"width": 1920, "height": 1080},
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            )

            self.login_with_cookies(context)

            # 首页热身
            p0 = context.new_page()
            p0.goto(self.url, wait_until="domcontentloaded")
            time.sleep(3)
            p0.close()

            for server_url in self.server_list:
                result = self.renew_server(context, server_url)
                sid = server_url.split("/")[-1]
                results.append(f"{sid}: {result}")
                time.sleep(15)

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