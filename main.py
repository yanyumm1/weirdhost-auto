import os
import time
from seleniumbase import SB

# --- 环境变量 ---
WEIRDHOST_EMAIL = os.environ.get("WEIRDHOST_EMAIL")
WEIRDHOST_PASSWORD = os.environ.get("WEIRDHOST_PASSWORD")
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

# --- 确保截图文件夹存在 ---
os.makedirs("screenshots", exist_ok=True)

def screenshot(sb, filename):
    path = os.path.join("screenshots", filename)
    sb.save_screenshot(path)
    print(f"📸 Screenshot saved: {path}")

def main():
    print("Weirdhost 自动续期脚本启动 ===\n")
    print("=== 启动 Xvfb + UC 模式 ===\n")

    try:
        with SB(uc=True, locale="en", test=True) as sb:
            print("🚀 浏览器启动（UC Mode）\n")

            # --- Cookie 登录 ---
            if REMEMBER_WEB_COOKIE:
                print("🔐 尝试使用 Cookie 登录...")
                sb.open("https://hub.weirdhost.xyz")
                time.sleep(2)
                try:
                    sb.add_cookie({
                        "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                        "value": REMEMBER_WEB_COOKIE,
                        "domain": "hub.weirdhost.xyz",
                        "path": "/",
                        "secure": True,
                        "httpOnly": True,
                    })
                    print("✅ Cookie 添加成功")
                except Exception as e:
                    print(f"⚠️ Cookie 添加失败: {e}")
                    screenshot(sb, "cookie_fail.png")

            # 跳转到目标服务器页面
            sb.open(SERVER_URL)
            time.sleep(2)
            screenshot(sb, "server_page.png")

            # --- 点击 '시간 추가' / Renew 按钮打开 Modal ---
            try:
                print("🕒 尝试打开 Renew Modal...")
                sb.wait_for_element_visible("button:has-text('시간 추가')", timeout=15)
                sb.click("button:has-text('시간 추가')")
                time.sleep(2)
                screenshot(sb, "01_modal_open.png")
            except Exception as e:
                print(f"❌ 打开 Modal 失败: {e}")
                screenshot(sb, "modal_open_fail.png")
                return

            # --- CF/Turnstile 盾交互 ---
            try:
                print("☑️ 尝试点击 Turnstile 盾...")
                sb.uc_gui_click_captcha()  # UC 模式自带方法处理 Turnstile
                time.sleep(4)
                screenshot(sb, "02_after_captcha.png")
            except Exception as e:
                print(f"⚠️ captcha 点击异常: {e}")
                screenshot(sb, "02_captcha_fail.png")

            # --- 查看 cookies（确认 cf_clearance） ---
            cookies = sb.get_cookies()
            cookie_names = [c["name"] for c in cookies]
            print("🍪 Cookies:", cookie_names)
            cf_clearance = next((c["value"] for c in cookies if c["name"] == "cf_clearance"), None)
            print("🧩 cf_clearance:", cf_clearance)
            if not cf_clearance:
                screenshot(sb, "03_no_cf_clearance.png")
                print("❌ 未获取 cf_clearance，可能 Cloudflare 未放行")
                return

            # --- 提交 Renew 表单 ---
            try:
                print("🚀 提交续期表单...")
                sb.execute_script("document.querySelector('#renew-modal form').submit();")
                time.sleep(3)
                screenshot(sb, "04_after_submit.png")
                print("ℹ️ 已尝试提交续期（结果需以后端为准）")
            except Exception as e:
                print(f"❌ 提交表单失败: {e}")
                screenshot(sb, "submit_fail.png")

            print("\n任务完成，浏览器关闭。")

    except Exception as e:
        print(f"❌ 脚本运行异常: {e}")

if __name__ == "__main__":
    main()