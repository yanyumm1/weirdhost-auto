import os
import time
from seleniumbase import SB
from pyvirtualdisplay import Display

# ---------- 配置 ----------
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL", "https://hub.weirdhost.xyz/server/a79a2b26")
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
WEIRDHOST_EMAIL = os.environ.get("WEIRDHOST_EMAIL")
WEIRDHOST_PASSWORD = os.environ.get("WEIRDHOST_PASSWORD")
SCREENSHOT_DIR = "screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def main():
    print("=== 启动 Xvfb + UC 模式 ===")
    with SB(uc=True, locale="en", test=True) as sb:
        print("🚀 浏览器启动（UC Mode）")

        try:
            # ---------- 优先 Cookie 登录 ----------
            if REMEMBER_WEB_COOKIE:
                print("检测到 REMEMBER_WEB_COOKIE，尝试 Cookie 登录...")
                sb.get(SERVER_URL)
                sb.add_cookie(
                    {"name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                     "value": REMEMBER_WEB_COOKIE,
                     "domain": "hub.weirdhost.xyz",
                     "path": "/",
                     "httpOnly": True,
                     "secure": True,
                     "sameSite": "Lax"}
                )
                sb.refresh()
                time.sleep(3)

                if "login" in sb.get_current_url() or "auth" in sb.get_current_url():
                    print("⚠ Cookie 登录失效，将回退邮箱密码登录")
                    REMEMBER_WEB_COOKIE = None
                else:
                    print("✅ Cookie 登录成功")

            # ---------- 邮箱密码登录 ----------
            if not REMEMBER_WEB_COOKIE:
                if not (WEIRDHOST_EMAIL and WEIRDHOST_PASSWORD):
                    print("❌ 缺少邮箱密码，无法登录")
                    return False

                login_url = "https://hub.weirdhost.xyz/auth/login"
                sb.get(login_url)
                time.sleep(3)

                # 打勾同意条款（年龄+隐私）
                checkbox_selector = "input[type='checkbox']"
                if sb.is_element_visible(checkbox_selector):
                    sb.click(checkbox_selector)
                    print("☑ 已打勾同意条款")

                # 填写邮箱密码
                sb.type('input[name="username"]', WEIRDHOST_EMAIL)
                sb.type('input[name="password"]', WEIRDHOST_PASSWORD)
                sb.click('button[type="submit"]')
                time.sleep(5)

                # 登录检查
                if "login" in sb.get_current_url() or "auth" in sb.get_current_url():
                    print("❌ 邮箱密码登录失败，截图保存")
                    sb.save_screenshot(f"{SCREENSHOT_DIR}/login_fail.png")
                    return False
                else:
                    print("✅ 邮箱密码登录成功")

            # ---------- 确保到达服务器页面 ----------
            if sb.get_current_url() != SERVER_URL:
                sb.get(SERVER_URL)
                time.sleep(3)
                if "login" in sb.get_current_url():
                    print("❌ 服务器页面访问失败，截图保存")
                    sb.save_screenshot(f"{SCREENSHOT_DIR}/server_page_fail.png")
                    return False

            # ---------- 点击 "시간 추가" ----------
            add_button_selector = 'button:has-text("시간 추가")'
            if sb.is_element_visible(add_button_selector):
                sb.click(add_button_selector)
                print("✅ 成功点击 '시간 추가'")
                time.sleep(5)
                sb.save_screenshot(f"{SCREENSHOT_DIR}/add_time_success.png")
                return True
            else:
                print("❌ 未找到 '시간 추가' 按钮，截图保存")
                sb.save_screenshot(f"{SCREENSHOT_DIR}/add_time_fail.png")
                return False

        except Exception as e:
            print(f"❌ 运行异常: {e}")
            sb.save_screenshot(f"{SCREENSHOT_DIR}/error.png")
            return False

if __name__ == "__main__":
    print("=== Weirdhost 自动续期脚本启动 ===")
    success = main()
    if success:
        print("🎉 任务执行成功")
        exit(0)
    else:
        print("⚠ 任务执行失败")
        exit(1)