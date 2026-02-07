import os
import time
import random
import platform
from seleniumbase import SB
from pyvirtualdisplay import Display

# =========================
# 环境变量
# =========================
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

# =========================
# 截图目录
# =========================
SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# =========================
# 工具函数
# =========================
def screenshot(sb, name):
    path = f"{SCREENSHOT_DIR}/{name}"
    try:
        sb.save_screenshot(path)
        print(f"📸 Screenshot saved: {path}")
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")

def human_sleep(a=1.2, b=2.8):
    time.sleep(random.uniform(a, b))

def wait_react_loaded(sb):
    sb.wait_for_ready_state_complete(timeout=30)
    human_sleep(2, 3)

def human_scroll(sb):
    try:
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.25)")
        human_sleep(1.5, 2.5)
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.55)")
        human_sleep(1.5, 2.5)
        sb.execute_script("window.scrollTo(0, 0)")
        human_sleep(1.0, 2.0)
    except Exception:
        pass

def remove_ads(sb):
    try:
        sb.execute_script("""
        document.querySelectorAll("iframe").forEach(f=>{
            const src = String(f.src || "");
            if (!src.includes("challenges.cloudflare.com")) {
                f.remove();
            }
        });
        """)
    except Exception:
        pass

# =========================
# Xvfb 支持（Linux） 
# =========================
def setup_xvfb():
    if platform.system().lower() == "linux" and not os.environ.get("DISPLAY"):
        display = Display(visible=False, size=(1920, 1080))
        display.start()
        os.environ["DISPLAY"] = display.new_display_var
        print("🖥️ Xvfb 已启动")
        return display
    return None

# =========================
# Renew / 시간 추가
# =========================
def click_time_add(sb):
    print("🖱️ 尝试点击 시간 추가 按钮")
    selectors = [
        '//button[span[contains(text(), "시간 추가")]]',
        '//button[contains(text(), "Renew")]'
    ]
    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=12)
            sb.scroll_to(sel)
            human_sleep()
            sb.click(sel)
            print(f"✅ 点击成功: {sel}")
            return True
        except Exception:
            continue
    return False

# =========================
# Turnstile 验证（修复点击失败）
# =========================
def solve_turnstile(sb, timeout=120):
    print("🛡️ 等待 Cloudflare Turnstile 放行 ...")
    start = time.time()
    attempt = 0

    while time.time() - start < timeout:
        attempt += 1
        try:
            # 已有 CF cookie
            cookies = sb.get_cookies()
            if any(c["name"] in ("cf_clearance", "__cf_bm") for c in cookies):
                print("✅ CF Cookie 已存在，Turnstile 放行")
                return True

            # iframe 检查
            iframe_count = sb.execute_script("""
            return document.querySelectorAll("iframe[src*='challenges.cloudflare.com']").length;
            """)
            if iframe_count == 0:
                print("✅ Turnstile iframe 未出现或已释放")
                return True

            # 尝试点击 iframe 内 checkbox
            try:
                clicked = sb.execute_script("""
                const frames = [...document.querySelectorAll("iframe[src*='challenges.cloudflare.com']")];
                if (frames.length === 0) return false;
                const f = frames[0];
                const rect = f.getBoundingClientRect();
                f.contentWindow.document.querySelectorAll("div, input").forEach(el => {
                    if (el.offsetParent) el.click();
                });
                return true;
                """)
                if clicked:
                    print(f"🖱️ Turnstile 点击尝试 {attempt}")
            except Exception:
                pass

        except Exception:
            pass

        if attempt % 3 == 0:
            screenshot(sb, f"cf_attempt_{attempt}.png")
        time.sleep(2)

    screenshot(sb, "cf_failed_timeout.png")
    print("❌ CF 超时未通过")
    return False

# =========================
# 主流程
# =========================
def main():
    print("🚀 Weirdhost 自动续期（UC + Xvfb + Turnstile）")

    if not SERVER_URL:
        raise Exception("❌ WEIRDHOST_SERVER_URL 未设置")

    display = setup_xvfb()
    try:
        with SB(
            uc=True,
            locale="en",
            headless=False,
            chromium_arg="--window-size=1920,1080"
        ) as sb:

            # 打开 Weirdhost 首页
            sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", reconnect_time=5)
            wait_react_loaded(sb)

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
                wait_react_loaded(sb)

            # 打开服务器页面
            print(f"📦 打开服务器页面: {SERVER_URL}")
            sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=5)
            wait_react_loaded(sb)
            remove_ads(sb)
            human_scroll(sb)
            screenshot(sb, "01_server_page.png")

            # 点击 시간 추가
            if not click_time_add(sb):
                screenshot(sb, "renew_not_found.png")
                raise Exception("❌ 时间追加按钮未找到")
            screenshot(sb, "02_after_first_click.png")

            # 处理 CF Turnstile
            if not solve_turnstile(sb):
                screenshot(sb, "cf_failed.png")
                raise Exception("❌ Cloudflare 未通过")
            screenshot(sb, "03_cf_passed.png")

            human_sleep(6, 10)
            screenshot(sb, "04_done.png")

            print("🎉 Weirdhost 自动续期完成")

    finally:
        if display:
            display.stop()

if __name__ == "__main__":
    main()