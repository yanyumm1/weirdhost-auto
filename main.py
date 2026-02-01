#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

WEIRDHOST_URL = "https://hub.weirdhost.xyz"

SERVER_URLS = [
    url.strip()
    for url in os.getenv("WEIRDHOST_SERVER_URLS", "").split(",")
    if url.strip()
]

REMEMBER_WEB_COOKIE = os.getenv("REMEMBER_WEB_COOKIE", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def wait_cf_turnstile_with_plugin(page, server_id, timeout=120):
    """
    插件版 CF 判断：
    1. 等 iframe 出现
    2. 等 iframe 消失（插件打勾）
    """
    log(f"🛡️ 服务器 {server_id} 等待 CF Turnstile（插件）")

    try:
        page.wait_for_selector(
            'iframe[src*="challenges.cloudflare.com"]',
            timeout=15000
        )
        log("⚠️ CF iframe 已出现")

        page.wait_for_selector(
            'iframe[src*="challenges.cloudflare.com"]',
            state="detached",
            timeout=timeout * 1000
        )

        log("✅ CF Turnstile 已通过")
        return True

    except TimeoutError:
        screenshot = f"cf_failed_{server_id}.png"
        page.screenshot(path=screenshot, full_page=True)
        log(f"❌ CF 未通过，已截图 {screenshot}")
        return False


def renew_server(page, server_url):
    server_id = server_url.rstrip("/").split("/")[-1]
    log(f"📦 处理服务器 {server_id}")

    page.goto(server_url, wait_until="networkidle")
    time.sleep(3)

    # 找续期按钮
    button = page.locator(
        'button:has-text("시간 추가"), button:has-text("시간추가")'
    ).first

    if not button.is_visible():
        page.screenshot(path=f"no_button_{server_id}.png", full_page=True)
        log("❌ 未找到续期按钮")
        return "no_button"

    log(f"🖱️ 点击续期按钮 ({server_id})")
    button.click(force=True)

    # ❗ 点击后才会出现 CF
    if not wait_cf_turnstile_with_plugin(page, server_id):
        return "cf_failed"

    # 等页面反馈
    time.sleep(5)
    page.reload(wait_until="networkidle")
    time.sleep(3)

    content = page.content()

    success_keywords = [
        "시간이 추가",
        "추가되었습니다",
        "success",
        "added"
    ]

    if any(k in content for k in success_keywords):
        log(f"✅ 服务器 {server_id} 续期成功")
        page.screenshot(path=f"renew_success_{server_id}.png", full_page=True)
        return "renew_success"

    if button.is_disabled():
        log(f"✅ 服务器 {server_id} 按钮已禁用，判定续期成功")
        return "renew_success"

    page.screenshot(path=f"renew_unknown_{server_id}.png", full_page=True)
    log(f"⚠️ 服务器 {server_id} 状态未知")
    return "renew_unknown"


def main():
    if not SERVER_URLS:
        raise RuntimeError("未设置 WEIRDHOST_SERVER_URLS")

    with sync_playwright() as p:
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            f"--disable-extensions-except={os.getcwd()}/captcha_solver",
            f"--load-extension={os.getcwd()}/captcha_solver",
        ]

        browser = p.chromium.launch(
            headless=HEADLESS,
            args=args
        )

        context = browser.new_context()
        page = context.new_page()

        # Cookie 登录
        if REMEMBER_WEB_COOKIE:
            log("🍪 使用 Cookie 登录")
            context.add_cookies([{
                "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                "value": REMEMBER_WEB_COOKIE,
                "domain": "hub.weirdhost.xyz",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }])

        page.goto(WEIRDHOST_URL, wait_until="domcontentloaded")
        time.sleep(3)

        log("✅ 登录成功")

        for server_url in SERVER_URLS:
            result = renew_server(page, server_url)
            log(f"结果: {result}")
            time.sleep(8)

        browser.close()


if __name__ == "__main__":
    log("🚀 Weirdhost 自动续期脚本启动")
    main()