import os
import time
from seleniumbase import SB
from pyvirtualdisplay import Display

# --- 配置 ---
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL", "https://hub.weirdhost.xyz/server/a79a2b26")
WEIRDHOST_EMAIL = os.environ.get("WEIRDHOST_EMAIL")
WEIRDHOST_PASSWORD = os.environ.get("WEIRDHOST_PASSWORD")
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SCREENSHOT_DIR = "screenshots"

if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

def main():
    global REMEMBER_WEB_COOKIE  # 修复 UnboundLocalError

    print("Weirdhost 自动续期脚本启动 ===")

    # 启动 Xvfb
    print("=== 启动 Xvfb + UC 模式 ===")
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    try:
        with SB(uc=True, locale="en", test=True) as sb:
            print("🚀 浏览器启动（UC Mode）")

            # --- 优先 Cookie 登录 ---
            cookie_login_success = False
            if REMEMBER_WEB_COOKIE:
                print("🔐 尝试使用 Cookie 登录...")
                sb.add_cookie({
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": REMEMBER_WEB_COOKIE,
                    "domain": "hub.weirdhost.xyz",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                })
                sb.open(SERVER_URL)
                time.sleep(3)

                # 检查是否被重定向到登录页
                if "login" in sb.get_current_url() or "auth" in sb.get_current_url():
                    print("⚠ Cookie 登录失败，将尝试邮箱密码登录")
                    REMEMBER_WEB_COOKIE = None
                else:
                    print("✅ Cookie 登录成功")
                    cookie_login_success = True

            # --- 邮箱密码登录 ---
            if not cookie_login_success:
                if not (WEIRDHOST_EMAIL and WEIRDHOST_PASSWORD):
                    print("❌ 缺少邮箱或密码，无法登录")
                    return False

                login_url = "https://hub.weirdhost.xyz/auth/login"
                print(f"🔐 使用邮箱密码登录: {login_url}")
                sb.open(login_url)
                time.sleep(2)

                # 填写邮箱密码
                sb.type('input[name="username"]', WEIRDHOST_EMAIL)
                sb.type('input[name="password"]', WEIRDHOST_PASSWORD)

                # 勾选首页条款 / CF盾
                checkbox_selector = 'input[type="checkbox"]'
                if sb.is_element_visible(checkbox_selector):
                    sb.click(checkbox_selector)
                    print("☑ 勾选同意条款 / CF盾")

                # 点击登录
                sb.click('button[type="submit"]')
                time.sleep(5)

                # 检查登录成功
                if "login" in sb.get_current_url() or "auth" in sb.get_current_url():
                    print("❌ 邮箱密码登录失败")
                    sb.save_screenshot(f"{SCREENSHOT_DIR}/login_fail.png")
                    return False
                else:
                    print("✅ 邮箱密码登录成功")

            # --- 确保在服务器页面 ---
            if sb.get_current_url() != SERVER_URL:
                sb.open(SERVER_URL)
                time.sleep(2)

            # --- 点击 시간 추가 按钮 ---
            add_button_selector = 'button:has-text("시간 추가")'
            if sb.is_element_visible(add_button_selector):
                sb.click(add_button_selector)
                print("⏱ 成功点击 '시간 추가' 按钮")
                time.sleep(5)
            else:
                print("❌ 未找到 '시간 추가' 按钮")
                sb.save_screenshot(f"{SCREENSHOT_DIR}/add_button_not_found.png")
                return False

            print("✅ 任务完成")
            return True

    except Exception as e:
        print(f"❌ 运行异常: {e}")
        try:
            sb.save_screenshot(f"{SCREENSHOT_DIR}/exception.png")
        except:
            pass
        return False
    finally:
        display.stop()


if __name__ == "__main__":
    success = main()
    if success:
        exit(0)
    else:
        exit(1)