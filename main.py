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

TIMEOUT_WAIT_CF = 60  # 等待 Cloudflare / Turnstile 完成的最长秒数
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
    print(f"⚠️ robust_click failed: {sel} err={last_err}")
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

def get_expiry(sb: SB) -> str:
    try:
        # 取 clock svg 后的文本
        text = sb.get_text('//p[svg[contains(@class,"fa-clock")]]').strip()
        expiry_time = text.split()[-1]  # "2026-02-09 11:49:29"
        return expiry_time
    except Exception:
        return ""

def wait_turnstile(sb: SB, timeout: int = TIMEOUT_WAIT_CF) -> bool:
    """
    等待 Turnstile iframe 消失或完成验证
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            iframes = sb.find_elements("iframe[src*='turnstile']")
            if not iframes:
                return True  # iframe 消失 => 通常验证完成
            else:
                # 尝试用 js 坐标点击 iframe 中的按钮
                for iframe in iframes:
                    rect = sb.get_element_rect(iframe)
                    if rect:
                        x = rect["x"] + rect["width"] / 2
                        y = rect["y"] + rect["height"] / 2
                        sb.driver.execute_script(f"window.scrollTo({x-400},{y-300});")
                        human_sleep(0.3,0.5)
                        sb.driver.execute_script(f"document.elementFromPoint({x},{y}).click();")
                        human_sleep(2,3)
        except Exception:
            human_sleep(1,1.5)
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

            # 记录点击前 Expiry
            expiry_before = get_expiry(sb)
            print("📅 当前 Expiry:", expiry_before)

            # 点击 시간 추가 / Renew 按钮
            if not click_time_add(sb):
                screenshot(sb, "renew_not_found.png")
                raise Exception("❌ 시간 추가 / Renew 按钮未找到")

            screenshot(sb, "02_after_click.png")

            # 等待 Turnstile / Cloudflare 验证
            print("⏳ 等待 Turnstile / Cloudflare 验证...")
            if not wait_turnstile(sb, timeout=60):
                print("⚠️ Turnstile / Cloudflare 验证超时")
            else:
                print("✅ Turnstile 弹窗已消失（通常表示验证已完成）")

            human_sleep(2, 3)
            sb.refresh()
            human_sleep(2, 3)

            # 记录点击后 Expiry
            expiry_after = get_expiry(sb)
            print("📅 点击后 Expiry:", expiry_after)

            screenshot(sb, "03_done.png")

            if expiry_after != expiry_before:
                print("🎉 自动续期流程完成 ✅ （Expiry 已更新）")
            else:
                print("⚠️ 自动续期流程完成，但 Expiry 未更新 ❌")
                raise Exception("❌ 续期失败")

    finally:
        if display:
            display.stop()

if __name__ == "__main__":
    main()