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

TIMEOUT_WAIT_CF = 60  # 等待 Cloudflare JS / Turnstile 完成的最长秒数

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
    try:
        cookies = sb.get_cookies()
        cf_clearance = next((c["value"] for c in cookies if c.get("name") == "cf_clearance"), None)
        print("🧩 cf_clearance:", "OK" if cf_clearance else "NONE")
        return bool(cf_clearance)
    except Exception:
        return False

def _robust_click(sb: SB, sel: str, tries: int = 3, sleep_s: float = 0.5) -> bool:
    last_err = None
    for _ in range(tries):
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

def click_time_add(sb: SB) -> bool:
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
# Turnstile 坐标点击核心
# =================================================
def click_turnstile_by_coord(sb: SB) -> bool:
    """
    尝试获取 Turnstile iframe 坐标并点击中间复选框
    """
    try:
        iframe_sel = "iframe[src*='turnstile']"
        if not sb.is_element_visible(iframe_sel):
            return False
        iframe = sb.find_element(iframe_sel)
        loc = iframe.location_once_scrolled_into_view
        size = iframe.size
        center_x = loc['x'] + size['width'] / 2
        center_y = loc['y'] + size['height'] / 2
        # 使用 JS 模拟鼠标事件点击 iframe 中心
        sb.execute_script(f"""
            var evt = new MouseEvent('click', {{
                bubbles: true,
                cancelable: true,
                view: window,
                clientX: {center_x},
                clientY: {center_y}
            }});
            document.elementFromPoint({center_x}, {center_y}).dispatchEvent(evt);
        """)
        print("🖱️ Turnstile iframe 坐标点击尝试")
        human_sleep(2, 3)
        return True
    except Exception as e:
        print(f"⚠️ Turnstile 坐标点击失败: {e}")
        return False

# =================================================
# 等待 Turnstile / Cloudflare 验证
# =================================================
def _wait_cloudflare_pass(sb: SB, timeout: int = TIMEOUT_WAIT_CF) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        # hidden input
        try:
            resp = sb.get_attribute("#cf-chl-widget-rjtfc_response", "value")
            if resp and resp.strip():
                print("✅ Turnstile hidden input 已填入")
                return True
        except Exception:
            pass

        if _has_cf_clearance(sb):
            return True

        # 坐标点击尝试
        click_turnstile_by_coord(sb)
        human_sleep(1.0, 2.0)

    print("⚠️ Cloudflare Turnstile 超时")
    return False

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

            # 点击 시간 추가 / Renew 按钮
            if not click_time_add(sb):
                screenshot(sb, "renew_not_found.png")
                raise Exception("❌ 시간 추가 / Renew 按钮未找到")
            screenshot(sb, "02_after_click.png")

            # 等待 Turnstile / Cloudflare 验证
            print("⏳ 等待 Turnstile / Cloudflare 验证...")
            if not _wait_cloudflare_pass(sb, timeout=TIMEOUT_WAIT_CF):
                screenshot(sb, "cf_failed.png")
                raise Exception("❌ Cloudflare 验证未通过")

            # 成功截图
            screenshot(sb, "03_done.png")
            print("🎉 Turnstile 验证完成 / 自动续期流程完成")

    finally:
        if display:
            display.stop()

if __name__ == "__main__":
    main()