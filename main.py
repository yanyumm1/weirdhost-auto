import os
import time
from seleniumbase import SB

# ========== 配置 ==========
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL", "https://hub.weirdhost.xyz/server/a79a2b26")
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"
EMAIL = os.environ.get("WEIRDHOST_EMAIL")
PASSWORD = os.environ.get("WEIRDHOST_PASSWORD")
SCREENSHOT_DIR = "screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def screenshot(sb, filename):
    path = f"{SCREENSHOT_DIR}/{filename}"
    sb.save_screenshot(path)
    print(f"📸 Screenshot saved: {path}")

def main():
    print("Weirdhost 自动续期脚本启动 ===\n")
    print("=== 启动 Xvfb + UC 模式 ===\n")

    with SB(uc=True, locale="en", test=True, headless=True) as sb:
        try:
            # ================= Cookie 登录 =================
            cookie_value = os.environ.get("WEIRDHOST_COOKIE")
            if cookie_value:
                print("🔐 尝试使用 Cookie 登录...")
                sb.open("https://hub.weirdhost.xyz")  # 先打开域名主页
                sb.add_cookie({
                    "name": COOKIE_NAME,
                    "value": cookie_value,
                    "domain": "hub.weirdhost.xyz",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "sameSite": "Lax",
                })
                sb.refresh()
                print("✅ Cookie 添加成功")
            else:
                print("⚠️ 未提供 Cookie，回退邮箱密码登录")
                sb.open("https://hub.weirdhost.xyz/auth/login")
                sb.wait_for_element_visible("input[name='username']", timeout=30)
                sb.type("input[name='username']", EMAIL)
                sb.type("input[name='password']", PASSWORD)
                sb.click("button[type='submit']")
                time.sleep(5)
            
            # ================= 打开服务器页面 =================
            sb.open(SERVER_URL)
            print("🌐 服务器页面打开")
            time.sleep(8)  # 等待 JS 渲染
            screenshot(sb, "server_page.png")

            # ================= 打开 Renew Modal =================
            try:
                print("🕒 尝试打开 Renew Modal...")
                sb.wait_for_element_visible("button:has-text('시간 추가')", timeout=30)
                sb.click("button:has-text('시간 추가')")
                time.sleep(2)
                screenshot(sb, "modal_open.png")
            except Exception as e:
                print(f"❌ 打开 Modal 失败: {e}")
                screenshot(sb, "modal_open_fail.png")
                return

            # ================= 处理 CF / Turnstile 盾 =================
            try:
                print("☑️ 尝试点击盾确认...")
                sb.uc_gui_click_captcha()
                time.sleep(4)
            except Exception as e:
                print(f"⚠️ 盾确认失败或未找到: {e}")
            screenshot(sb, "after_captcha.png")

            # ================= 检查 CF Cookie =================
            cookies = sb.get_cookies()
            cf_clearance = next((c["value"] for c in cookies if c["name"] == "cf_clearance"), None)
            print("🧩 cf_clearance:", cf_clearance)
            if not cf_clearance:
                screenshot(sb, "no_cf_clearance.png")
                print("❌ 未获取 cf_clearance（Cloudflare 可能未放行）")

            # ================= 提交 Renew =================
            try:
                sb.execute_script("document.querySelector('#renew-modal form').submit();")
                time.sleep(3)
                screenshot(sb, "after_submit.png")
                print("ℹ️ 已尝试提交续期（结果需以后端为准）")
            except Exception as e:
                print(f"❌ 提交续期失败: {e}")
                screenshot(sb, "submit_fail.png")

            print("\n任务完成。浏览器关闭。")

        except Exception as e:
            print(f"❌ 运行异常: {e}")
            screenshot(sb, "general_error.png")

if __name__ == "__main__":
    main()