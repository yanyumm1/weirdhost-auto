import os
import time
from seleniumbase import SB

# 从环境变量获取登录信息
WEIRDHOST_EMAIL = os.environ.get("WEIRDHOST_EMAIL")
WEIRDHOST_PASSWORD = os.environ.get("WEIRDHOST_PASSWORD")
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")  # 你的目标服务器页面

# 确保 screenshots 文件夹存在
os.makedirs("screenshots", exist_ok=True)

def main():
    print("Weirdhost 自动续期脚本启动 ===\n")
    print("=== 启动 Xvfb + UC 模式 ===\n")

    try:
        # UC 模式启动浏览器
        with SB(uc=True, locale="en", test=True) as sb:
            print("🚀 浏览器启动（UC Mode）\n")

            # --- Cookie 登录 ---
            if REMEMBER_WEB_COOKIE:
                print("🔐 尝试使用 Cookie 登录...")
                try:
                    # 先打开首页，确保域名匹配
                    sb.open("https://hub.weirdhost.xyz")
                    time.sleep(2)

                    sb.add_cookie({
                        "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                        "value": REMEMBER_WEB_COOKIE,
                        "domain": "hub.weirdhost.xyz",
                        "path": "/",
                        "secure": True,
                        "httpOnly": True,
                    })
                    print("✅ Cookie 添加成功")

                    # 跳转到服务器页面
                    sb.open(SERVER_URL)
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Cookie 登录失败: {e}")
                    sb.save_screenshot("screenshots/cookie_fail.png")

            # --- 邮箱密码登录（如果没有 Cookie 或 Cookie 失效） ---
            else:
                print("🔐 使用邮箱密码登录...")
                sb.open("https://hub.weirdhost.xyz/auth/login")
                time.sleep(2)
                try:
                    sb.type('input[name="username"]', WEIRDHOST_EMAIL)
                    sb.type('input[name="password"]', WEIRDHOST_PASSWORD)
                    sb.click('button[type="submit"]')
                    time.sleep(3)

                    # 检查登录是否成功
                    if "login" in sb.get_current_url():
                        print("❌ 邮箱密码登录失败")
                        sb.save_screenshot("screenshots/login_fail.png")
                    else:
                        print("✅ 邮箱密码登录成功")
                except Exception as e:
                    print(f"❌ 登录异常: {e}")
                    sb.save_screenshot("screenshots/login_error.png")

            # --- 打勾盾操作 ---
            try:
                print("☑️ 尝试点击盾确认...")
                # 假设盾是一个 checkbox 或按钮
                sb.wait_for_element_visible('input[type="checkbox"]', timeout=15)
                sb.click('input[type="checkbox"]')
                time.sleep(1)
                sb.save_screenshot("screenshots/checked_cf_shield.png")
                print("✅ 盾确认完成")
            except Exception as e:
                print(f"⚠️ 盾确认失败或未找到: {e}")

            # --- 点击 '시간 추가' 按钮 ---
            try:
                print("🕒 尝试点击 '시간 추가' 按钮...")
                sb.wait_for_element_visible('button:has-text("시간 추가")', timeout=15)
                sb.click('button:has-text("시간 추가")')
                time.sleep(2)
                sb.save_screenshot("screenshots/add_time_done.png")
                print("✅ 서버 시간 추가完成")
            except Exception as e:
                print(f"❌ 点击 '시간 추가' 失败: {e}")
                sb.save_screenshot("screenshots/add_time_fail.png")

            print("\n任务完成。浏览器关闭。")

    except Exception as e:
        print(f"❌ 脚本运行异常: {e}")

if __name__ == "__main__":
    main()