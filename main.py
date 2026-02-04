import os
import time
from seleniumbase import SB

WEIRDHOST_EMAIL = os.environ.get("WEIRDHOST_EMAIL")
WEIRDHOST_PASSWORD = os.environ.get("WEIRDHOST_PASSWORD")
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

os.makedirs("screenshots", exist_ok=True)

def screenshot(sb, filename):
    path = os.path.join("screenshots", filename)
    sb.save_screenshot(path)
    print(f"📸 Screenshot saved: {path}")

def wait_page_loaded(sb, timeout=30):
    sb.wait_for_ready_state_complete(timeout=timeout)

def click_renew_button(sb):
    print("🕒 尝试寻找 Renew 按钮...")

    renew_xpaths = [
        "//button[contains(., '시간 추가')]",
        "//button[contains(., 'Renew')]",
        "//button[contains(., 'Extend')]",
        "//button[contains(., 'Add time')]",
    ]

    for xp in renew_xpaths:
        try:
            sb.wait_for_element_visible(f"xpath={xp}", timeout=5)
            sb.scroll_to(f"xpath={xp}")
            sb.click(f"xpath={xp}")
            print(f"✅ 找到按钮: {xp}")
            return True
        except:
            pass

    return False

def main():
    print("Weirdhost 自动续期脚本启动 ===")

    try:
        with SB(uc=True, locale="en", test=True) as sb:

            print("🚀 浏览器启动")

            sb.set_window_size(1920, 1080)

            # --- Cookie 登录 ---
            if REMEMBER_WEB_COOKIE:
                print("🔐 Cookie 登录")

                sb.open("https://hub.weirdhost.xyz")
                wait_page_loaded(sb)

                sb.add_cookie({
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": REMEMBER_WEB_COOKIE,
                    "domain": "hub.weirdhost.xyz",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                })

                sb.refresh()
                wait_page_loaded(sb)

            # --- 打开服务器页面 ---
            sb.open(SERVER_URL)
            wait_page_loaded(sb)
            time.sleep(3)

            screenshot(sb, "server_page.png")

            # --- 点击续期 ---
            if not click_renew_button(sb):
                print("❌ 未找到续期按钮")
                screenshot(sb, "modal_open_fail.png")
                return

            time.sleep(2)
            screenshot(sb, "01_modal_open.png")

            # --- Turnstile ---
            try:
                print("☑️ 处理 Cloudflare")
                sb.uc_gui_click_captcha()
                time.sleep(5)
                screenshot(sb, "02_after_captcha.png")
            except Exception as e:
                print("⚠️ captcha 可能未出现:", e)

            # --- 检查 cf_clearance ---
            cookies = sb.get_cookies()
            cf = next((c["value"] for c in cookies if c["name"] == "cf_clearance"), None)

            if not cf:
                print("❌ 未通过 Cloudflare")
                screenshot(sb, "03_no_cf_clearance.png")
                return

            print("✅ Cloudflare 已通过")

            # --- 提交续期 ---
            try:
                sb.execute_script("""
                document.querySelector('#renew-modal form')?.submit()
                """)
                time.sleep(3)
                screenshot(sb, "04_after_submit.png")
                print("🚀 已提交续期")
            except Exception as e:
                print("❌ 提交失败:", e)

    except Exception as e:
        print("❌ 运行异常:", e)

if __name__ == "__main__":
    main()