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

TIMEOUT_WAIT_CF = 90        # Turnstile/CF 验证最长等待秒数
CLICK_RETRY_INTERVAL = 3    # 每次尝试点击间隔
MAX_CLICK_TRIES = 10        # 最多点击次数（防止无限循环）

TURNSTILE_IFRAME_SELECTOR = "iframe[src*='turnstile']"
TURNSTILE_HIDDEN_SELECTOR = "input[name='cf-turnstile-response']"

# =================================================
# 工具函数
# =================================================
def human_sleep(a=0.8, b=1.6):
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


def _get_turnstile_hidden_value(sb: SB) -> str:
    """
    Weirdhost 页面里存在：
    <input type="hidden" name="cf-turnstile-response" ...>
    """
    try:
        val = sb.get_attribute(TURNSTILE_HIDDEN_SELECTOR, "value")
        if val:
            val = val.strip()
        return val or ""
    except Exception:
        return ""


def _robust_click(sb: SB, sel: str, tries: int = 3) -> bool:
    last_err = None
    for t in range(1, tries + 1):
        try:
            sb.scroll_to(sel)
            human_sleep(0.2, 0.5)
            sb.click(sel)
            human_sleep(0.8, 1.2)
            return True
        except Exception as e1:
            last_err = e1
            try:
                sb.execute_script(
                    "var el=document.evaluate(arguments[0], document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;"
                    "if(el){el.click(); return true;} return false;",
                    sel
                )
                human_sleep(0.8, 1.2)
                return True
            except Exception as e2:
                last_err = e2
                human_sleep(0.5, 0.9)

    print(f"⚠️ robust_click 失败: {sel} err={last_err}")
    return False


def click_time_add(sb: SB) -> bool:
    selectors = [
        '//button[span[contains(text(), "시간 추가")]]',
        '//button[contains(text(), "시간 추가")]',
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
    print("❌ 找不到 시간 추가 / Renew 按钮")
    return False


def setup_xvfb():
    if platform.system().lower() == "linux" and not os.environ.get("DISPLAY"):
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=False, size=(1920, 1080))
            display.start()
            os.environ["DISPLAY"] = display.new_display_var
            print("🖥️ Xvfb 已启动")
            return display
        except ImportError:
            print("⚠️ 请安装 pyvirtualdisplay 和 xvfb")
            return None
    return None


# =================================================
# Turnstile iframe 坐标点击
# =================================================
def try_click_turnstile(sb: SB) -> bool:
    """
    目标：
    - 找到 Turnstile iframe
    - 计算 iframe 中央偏左（更接近 checkbox）
    - 用 uc_gui_click_x_y 点击
    """
    if not sb.is_element_visible(TURNSTILE_IFRAME_SELECTOR):
        print("⚠️ Turnstile iframe 不可见")
        return False

    try:
        iframe = sb.find_element(TURNSTILE_IFRAME_SELECTOR)

        # location_once_scrolled_into_view 更靠谱
        loc = iframe.location_once_scrolled_into_view
        size = iframe.size

        x = loc.get("x", 0)
        y = loc.get("y", 0)
        w = size.get("width", 0)
        h = size.get("height", 0)

        print(f"🎯 Turnstile iframe 坐标: x={x} y={y} w={w} h={h}")

        if w < 20 or h < 20:
            print("⚠️ iframe size 太小，不点击")
            return False

        # Turnstile checkbox 一般在 iframe 内偏左区域
        click_x = int(x + w * 0.25)
        click_y = int(y + h * 0.50)

        print(f"🖱️ 计算点击坐标: click_x={click_x}, click_y={click_y}")

        # 关键：用 UC 模式 GUI 点击（真实鼠标点击）
        sb.uc_gui_click_x_y(click_x, click_y)
        print("✅ 已执行 uc_gui_click_x_y 点击 Turnstile")

        human_sleep(1.2, 2.0)
        return True

    except Exception as e:
        print(f"⚠️ Turnstile 坐标点击失败: {e}")
        return False


# =================================================
# 等待 Cloudflare / Turnstile 放行（核心）
# =================================================
def wait_turnstile_pass(sb: SB, timeout: int = TIMEOUT_WAIT_CF) -> bool:
    """
    成功条件（满足任意一个）：
    - hidden input cf-turnstile-response 有值
    - cf_clearance cookie 出现
    - Turnstile iframe 消失（通常表示已验证）
    """
    start = time.time()
    click_count = 0

    while time.time() - start < timeout:
        elapsed = int(time.time() - start)

        hidden_val = _get_turnstile_hidden_value(sb)
        if hidden_val:
            print(f"✅ Turnstile hidden input 已填入 (len={len(hidden_val)})")
            return True

        if _has_cf_clearance(sb):
            print("✅ cf_clearance 已出现，Cloudflare 已放行")
            return True

        iframe_visible = sb.is_element_visible(TURNSTILE_IFRAME_SELECTOR)

        if not iframe_visible:
            # iframe 消失有可能表示验证通过，也可能是页面结构变化
            print("✅ Turnstile iframe 已消失（通常表示验证已完成）")
            return True

        # 如果 iframe 还在，就尝试点击
        if click_count < MAX_CLICK_TRIES:
            click_count += 1
            print(f"🔁 第 {click_count}/{MAX_CLICK_TRIES} 次尝试点击 Turnstile... (elapsed={elapsed}s)")
            clicked = try_click_turnstile(sb)
            screenshot(sb, f"turnstile_click_try_{click_count:02d}.png")

            if not clicked:
                print("⚠️ 点击失败（可能 iframe 被遮挡或没加载完全）")

        else:
            print("⚠️ 点击次数达到上限，不再点击，只等待...")
            human_sleep(2, 3)

        time.sleep(CLICK_RETRY_INTERVAL)

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

            # 打开首页（建立域）
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

            # 点击 시간 추가
            if not click_time_add(sb):
                screenshot(sb, "renew_not_found.png")
                raise Exception("❌ 시간 추가 / Renew 按钮未找到")

            screenshot(sb, "02_after_click.png")

            # 等待 Turnstile
            print("⏳ 等待 Turnstile / Cloudflare 验证...")

            ok = wait_turnstile_pass(sb, timeout=TIMEOUT_WAIT_CF)

            if not ok:
                print("❌ Cloudflare / Turnstile 验证超时")
                screenshot(sb, "cf_failed.png")
                raise Exception("❌ Cloudflare 验证未通过")

            # 最终截图
            screenshot(sb, "03_done.png")
            print("🎉 自动续期流程完成（Turnstile 已通过）")

    finally:
        if display:
            display.stop()


if __name__ == "__main__":
    main()