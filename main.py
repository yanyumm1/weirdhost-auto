#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import random
import platform
from pathlib import Path
from seleniumbase import SB

# =================================================
# 配置
# =================================================
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")

TIMEOUT_WAIT_CF = 60  # 等待 Cloudflare JS 完成的最长秒数
RETRY_REFRESH_INTERVAL = 5  # 每次尝试刷新间隔（秒）

# =================================================
# 工具函数
# =================================================
def human_sleep(a=1.0, b=2.5):
    time.sleep(random.uniform(a, b))

def screenshot(sb, name: str):
    path = SCREENSHOT_DIR / name
    try:
        sb.save_screenshot(str(path))
        print(f"📸 Screenshot saved: {path}")
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")

def _has_cf_clearance(sb: SB) -> bool:
    """
    检查 cf_clearance 是否存在（用于判断 Cloudflare 是否放行）
    """
    try:
        cookies = sb.get_cookies()
        cf_clearance = next((c["value"] for c in cookies if c.get("name") == "cf_clearance"), None)
        print("🧩 cf_clearance:", "OK" if cf_clearance else "NONE")
        return bool(cf_clearance)
    except Exception:
        return False

def _robust_click(sb: SB, sel: str, tries: int = 3, sleep_s: float = 0.5) -> bool:
    """
    更稳的点击函数：滚动 + 尝试 JS click 兜底
    """
    last_err = None
    for t in range(1, tries + 1):
        try:
            sb.scroll_to(sel)
            human_sleep(0.1, 0.3)
            sb.click(sel)
            human_sleep(sleep_s, sleep_s + 0.3)
            return True
        except Exception as e1:
            last_err = e1
            try:
                sb.execute_script(
                    "var el=document.querySelector(arguments[0]); if(el){el.click(); return true;} return false;",
                    sel,
                )
                human_sleep(sleep_s, sleep_s + 0.3)
                return True
            except Exception as e2:
                last_err = e2
                human_sleep(0.2, 0.4)
    print(f"⚠️ robust_click 失败：{sel} err={last_err}")
    return False

def _wait_cloudflare_pass(sb: SB, timeout: int = TIMEOUT_WAIT_CF) -> bool:
    """
    等待 Cloudflare JS 完成（Managed Challenge / Turnstile）
    """
    start = time.time()
    while time.time() - start < timeout:
        page_source = sb.get_page_source().lower()
        challenge_indicators = [
            "just a moment",
            "checking your browser",
            "verify you are human",
            "cf-browser-verification",
            "cloudflare",
        ]
        if not any(x in page_source for x in challenge_indicators):
            if _has_cf_clearance(sb):
                return True
            else:
                # 有时 Managed Challenge 不立即下发 cf_clearance
                return True
        human_sleep(1.0, 2.0)
    return False

def click_time_add(sb: SB) -> bool:
    """
    点击 Weirdhost “시간 추가” 按钮（或 Renew）
    """
    selectors = [
        '//button[span[contains(text(), "시간 추가")]]',
        '//button[contains(text(), "Renew")]'
    ]
    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=10)
            if _robust_click(sb, sel):
                print(f"✅ 点击成功: {sel}")
                return True
        except Exception:
            continue
    print("⚠️ 시간 추가 / Renew 按钮未找到")
    return False

def setup_xvfb():
    """Linux 下启用虚拟显示"""
    if platform.system().lower() == "linux" and not os.environ.get("DISPLAY"):
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=False, size=(1920,1080))
            display.start()
            os.environ["DISPLAY"] = display.new_display_var
            print("🖥️ Xvfb 已启动")
            return display
        except ImportError:
            print("请安装 pyvirtualdisplay 和 xvfb")
            return None
    return None

# =================================================
# 主流程
# =================================================
def main():
    if not SERVER_URL:
        raise Exception("❌ WEIRDHOST_SERVER_URL 未设置")

    display = setup_xvfb()

    try:
        with SB(
            uc=True,
            headless=False,
            locale="en",
            chromium_arg="--no-sandbox --disable-blink-features=AutomationControlled --window-size=1920,1080"
        ) as sb:

            print("🚀 Weirdhost 自动续期启动")

            # 首页
            sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", reconnect_time=5)
            human_sleep(1, 2)

            # Cookie 登录
            if REMEMBER_WEB_COOKIE:
                print("🍪 注入 Cookie 登录")
                sb.add_cookie({
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": REMEMBER_WEB_COOKIE,
                    "domain": "hub.weirdhost.xyz",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                })
                sb.refresh()
                human_sleep(2, 3)

            # 打开服务器页面
            print(f"📦 打开服务器页面: {SERVER_URL}")
            sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=5)
            human_sleep(2, 3)
            screenshot(sb, "01_server_page.png")

            # -------------------------------
            # 点击 시간 추가 / Renew 按钮
            # -------------------------------
            if not click_time_add(sb):
                screenshot(sb, "renew_not_found.png")
                raise Exception("❌ 시간 추가 / Renew 按钮未找到")

            screenshot(sb, "02_after_click.png")

            # -------------------------------
            # 等待弹窗 / challenge 放行
            # -------------------------------
            print("⏳ 等待弹窗 Cloudflare challenge 放行...")
            # 假设弹窗类名包含 renew-popup
            try:
                sb.wait_for_element_visible("//div[contains(@class,'renew-popup')]", timeout=10)
                human_sleep(1,2)
            except Exception:
                print("⚠️ 弹窗未出现，可能已自动跳过")

            if not _wait_cloudflare_pass(sb, timeout=60):
                print("⚠️ 弹窗 Cloudflare challenge 超时")
            else:
                print("✅ 弹窗 Cloudflare 已放行 / cf_clearance OK")

            # -------------------------------
            # 完成截图
            # -------------------------------
            screenshot(sb, "03_done.png")
            print("🎉 自动续期流程完成")

    finally:
        if display:
            display.stop()

if __name__ == "__main__":
    main()