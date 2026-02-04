import os
import time
from seleniumbase import SB
from pyvirtualdisplay import Display

# -------------------------------
# 配置环境变量
# -------------------------------
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
WEIRDHOST_EMAIL = os.environ.get("WEIRDHOST_EMAIL")
WEIRDHOST_PASSWORD = os.environ.get("WEIRDHOST_PASSWORD")
WEIRDHOST_SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL", "https://hub.weirdhost.xyz/server/a79a2b26")

def main():
    print("Weirdhost 自动续期脚本启动 ===")
    print("\n=== 启动 Xvfb + UC 模式 ===")

    # -------------------------------
    # 启动 UC 模式浏览器
    # -------------------------------
    try:
        with SB(uc=True, locale="en", test=True) as sb:
            print("🚀 浏览器启动（UC Mode）")

            # -------------------------------
            # 先尝试 Cookie 登录
            # -------------------------------
            if REMEMBER_WEB_COOKIE:
                print("🔐 尝试使用 REMEMBER_WEB_COOKIE 登录...")
                sb.open("https://hub.weirdhost.xyz")
                # 设置 Cookie
                sb.add_cookie({
                    'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                    'value': REMEMBER_WEB_COOKIE,
                    'domain': 'hub.weirdhost.xyz',
                    'path': '/',
                    'secure': True,
                    'httpOnly': True,
                    'sameSite': 'Lax',
                })
                sb.refresh()
                time.sleep(3)

                # 判断是否登录成功
                if "login" in sb.get_current_url() or "auth" in sb.get_current_url():
                    print("⚠ Cookie 登录失败，将尝试邮箱密码登录")
                    REMEMBER_WEB_COOKIE = None
                    sb.delete_all_cookies()
                else:
                    print("✅ Cookie 登录成功")

            # -------------------------------
            # 如果 Cookie 失败或不存在，用邮箱密码登录
            # -------------------------------
            if not REMEMBER_WEB_COOKIE:
                if not (WEIRDHOST_EMAIL and WEIRDHOST_PASSWORD):
                    print("❌ 未提供登录信息，无法登录")
                    return False

                print("🔐 使用邮箱密码登录 Weirdhost")
                sb.open("https://hub.weirdhost.xyz/auth/login")
                sb.wait_for_element('input[name="username"]')
                sb.type('input[name="username"]', WEIRDHOST_EMAIL)
                sb.type('input[name="password"]', WEIRDHOST_PASSWORD)
                
                # 如果有打勾的 CF盾，需要点击勾选
                try:
                    cf_checkbox_selector = 'input[type="checkbox"]'
                    sb.wait_for_element(cf_checkbox_selector, timeout=10)
                    sb.click(cf_checkbox_selector)
                    print("☑️ CF盾勾选完成")
                except Exception:
                    print("ℹ️ 没有检测到 CF盾勾选框")

                # 点击登录
                sb.click('button[type="submit"]')
                time.sleep(3)

                # 判断是否登录成功
                if "login" in sb.get_current_url() or "auth" in sb.get_current_url():
                    print("❌ 登录失败，请检查邮箱密码")
                    sb.save_screenshot("screenshots/login_fail.png")
                    return False
                else:
                    print("✅ 邮箱密码登录成功")

            # -------------------------------
            # 打开服务器页面并点击 "시간 추가"
            # -------------------------------
            sb.open(WEIRDHOST_SERVER_URL)
            sb.wait_for_element('button:has-text("시간 추가")', timeout=30)
            sb.click('button:has-text("시간 추가")')
            print("✅ 成功点击 '시간 추가' 按钮")
            sb.save_screenshot("screenshots/add_time_success.png")
            time.sleep(2)

            print("🚀 任务完成")
            return True

    except Exception as e:
        print(f"❌ 运行异常: {e}")
        try:
            sb.save_screenshot("screenshots/error.png")
        except:
            pass
        return False

if __name__ == "__main__":
    os.makedirs("screenshots", exist_ok=True)
    success = main()
    if success:
        print("任务执行成功")
        exit(0)
    else:
        print("任务执行失败")
        exit(1)