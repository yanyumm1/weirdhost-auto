import os
import time
from seleniumbase import SB

REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

os.makedirs("screenshots", exist_ok=True)


def screenshot(sb, name):
    path = f"screenshots/{name}"
    sb.save_screenshot(path)
    print(f"📸 Screenshot saved: {path}")


def wait_react_loaded(sb):
    sb.wait_for_ready_state_complete(timeout=30)
    sb.sleep(4)


def remove_ads(sb):
    sb.execute_script("""
    document.querySelectorAll("iframe").forEach(f=>f.remove())
    """)


def click_renew_button(sb):
    print("🕒 查找 Renew 按钮")

    selectors = [
        'button[color="primary"]',
        'div[class*="RenewBox"] button'
    ]

    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=12)
            sb.scroll_to(sel)
            sb.click(sel)
            print(f"✅ 点击成功: {sel}")
            return True
        except Exception:
            pass

    # JS fallback
    try:
        sb.execute_script("""
        document.querySelectorAll('button[color="primary"]')
        .forEach(btn => btn.click())
        """)
        return True
    except:
        pass

    return False


def main():
    print("=== Weirdhost 自动续期启动 ===")

    with SB(
        uc=True,
        locale="en",
        test=True,
        headless=False,
        chromium_arg="--window-size=1920,1080"
    ) as sb:

        print("🚀 浏览器启动")

        sb.open("https://hub.weirdhost.xyz")
        wait_react_loaded(sb)

        # ---------- Cookie 登录 ----------
        if REMEMBER_WEB_COOKIE:
            print("🔐 Cookie 登录")

            sb.add_cookie({
                "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                "value": REMEMBER_WEB_COOKIE,
                "domain": "hub.weirdhost.xyz",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            })

            sb.refresh()
            wait_react_loaded(sb)

        # ---------- 打开服务器 ----------
        sb.open(SERVER_URL)
        wait_react_loaded(sb)
        remove_ads(sb)

        screenshot(sb, "server_page.png")

        # ---------- 点击续期 ----------
        if not click_renew_button(sb):
            print("❌ 未找到 Renew 按钮")
            screenshot(sb, "renew_not_found.png")
            return

        sb.sleep(3)
        screenshot(sb, "modal_open.png")

        # ---------- Cloudflare ----------
        try:
            print("☑️ 尝试通过 Cloudflare")
            sb.uc_gui_click_captcha()
            sb.sleep(5)
        except Exception:
            print("⚠️ 未检测到验证码")

        screenshot(sb, "after_cf.png")

        # ---------- 提交表单 ----------
        try:
            sb.execute_script("""
            document.querySelector('#renew-modal form')?.submit()
            """)
            print("🚀 已提交续期")
        except Exception as e:
            print("❌ 提交失败", e)

        sb.sleep(4)
        screenshot(sb, "after_submit.png")

        print("=== 任务完成 ===")


if __name__ == "__main__":
    main()