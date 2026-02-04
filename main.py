#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import platform
from seleniumbase import SB
from pyvirtualdisplay import Display


# ================== 配置 ==================
WEIRDHOST_EMAIL = os.getenv("PTERODACTYL_EMAIL")
WEIRDHOST_PASSWORD = os.getenv("PTERODACTYL_PASSWORD")

LOGIN_URL = "https://hub.weirdhost.xyz/auth/login"
SERVER_URL = "https://hub.weirdhost.xyz/server/a79a2b26"

SCREENSHOT_DIR = "screenshots"


# ================== 工具函数 ==================
def setup_xvfb():
    if platform.system().lower() == "linux" and not os.environ.get("DISPLAY"):
        display = Display(visible=False, size=(1920, 1080))
        display.start()
        os.environ["DISPLAY"] = display.new_display_var
        print("🖥️ Xvfb 已启动")
        return display
    return None


def screenshot(sb, name):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = f"{SCREENSHOT_DIR}/{name}.png"
    sb.save_screenshot(path)
    print(f"📸 {path}")


def has_cf_clearance(sb) -> bool:
    return any(c["name"] == "cf_clearance" for c in sb.get_cookies())


# ================== 主流程 ==================
def main():
    if not WEIRDHOST_EMAIL or not WEIRDHOST_PASSWORD:
        raise RuntimeError("❌ 缺少 Weirdhost 登录环境变量")

    display = setup_xvfb()

    try:
        with SB(uc=True, locale="en", test=True) as sb:
            print("🚀 浏览器启动（UC Mode）")

            # ---------- 登录 ----------
            print("🔐 登录 Weirdhost")
            sb.open(LOGIN_URL)
            sb.wait_for_element_visible('input[name="username"]', timeout=20)

            sb.type('input[name="username"]', WEIRDHOST_EMAIL)
            sb.type('input[name="password"]', WEIRDHOST_PASSWORD)
            sb.click('button[type="submit"]')

            sb.wait_for_element_visible("body", timeout=20)
            time.sleep(2)
            screenshot(sb, "01_after_login")

            # ---------- 打开服务器页面 ----------
            print("🔁 打开服务器页面")
            sb.open(SERVER_URL)
            sb.wait_for_element_visible("body", timeout=20)
            time.sleep(2)
            screenshot(sb, "02_server_page_loaded")

            # ---------- 第一次 Cloudflare（如果有） ----------
            print("🛡️ 检查 Cloudflare（页面级）")
            try:
                sb.uc_gui_click_captcha()
                time.sleep(4)
            except Exception as e:
                print(f"ℹ️ 页面 CF 无需处理或已通过: {e}")

            screenshot(sb, "03_after_page_cf")

            # ---------- 点击「시간 추가」 ----------
            print("🖱️ 查找并点击「시간 추가」")
            add_btn = sb.find_element("//button[contains(text(),'시간')]")
            if not add_btn.is_enabled():
                print("⏭️ 按钮不可点击（可能未到续期时间）")
                screenshot(sb, "04_button_disabled")
                return

            add_btn.click()
            time.sleep(2)
            screenshot(sb, "05_after_click_add")

            # ---------- 第二次 Cloudflare（关键！） ----------
            print("🛡️ 处理 시간 추가后的 Cloudflare")
            try:
                sb.uc_gui_click_captcha()
                time.sleep(5)
            except Exception as e:
                print(f"ℹ️ 第二次 CF 可能已自动通过: {e}")

            screenshot(sb, "06_after_turnstile_check")

            # ---------- 结果确认 ----------
            cookies = sb.get_cookies()
            print("🍪 Cookies:", [c["name"] for c in cookies])

            if has_cf_clearance(sb):
                print("🧩 cf_clearance 已存在（CF 通过）")
            else:
                print("⚠️ 未检测到 cf_clearance（但不一定失败）")

            screenshot(sb, "07_final_state")
            print("🎉 已尝试完成 Weirdhost 时间追加（结果以后端为准）")

    finally:
        if display:
            display.stop()


if __name__ == "__main__":
    main()