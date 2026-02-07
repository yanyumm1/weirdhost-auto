import os
import time
import random
import platform
from seleniumbase import SB

# =========================
# pyvirtualdisplay 可选
# =========================
try:
    from pyvirtualdisplay import Display
    HAS_XVFB = True
except ImportError:
    Display = None
    HAS_XVFB = False

# =========================
# 环境变量
# =========================
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# =========================
# 工具函数
# =========================
def log(msg):
    print(msg, flush=True)

def screenshot(sb, name):
    path = f"{SCREENSHOT_DIR}/{name}"
    try:
        sb.save_screenshot(path)
        log(f"📸 Screenshot saved: {path}")
    except Exception as e:
        log(f"⚠️ Screenshot failed: {e}")

def human_sleep(a=1.2, b=2.8):
    time.sleep(random.uniform(a, b))

def wait_react_loaded(sb):
    sb.wait_for_ready_state_complete(timeout=30)
    human_sleep(2, 3)

def human_scroll(sb):
    try:
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.4)")
        human_sleep()
        sb.execute_script("window.scrollTo(0, 0)")
    except Exception:
        pass

def remove_ads(sb):
    try:
        sb.execute_script("""
        document.querySelectorAll("iframe").forEach(f=>{
            if (!(f.src||"").includes("challenges.cloudflare.com")) {
                f.remove();
            }
        });
        """)
    except Exception:
        pass

# =========================
# Xvfb（可选）
# =========================
def setup_xvfb():
    if platform.system().lower() == "linux" and not os.environ.get("DISPLAY") and HAS_XVFB:
        display = Display(visible=False, size=(1920, 1080))
        display.start()
        os.environ["DISPLAY"] = display.new_display_var
        log("🖥️ Xvfb 已启动")
        return display
    return None

# =========================
# 点击「시간 추가」
# =========================
def click_time_add(sb):
    log("🖱️ 尝试点击 시간 추가")
    selectors = [
        '//button[span[contains(text(), "시간 추가")]]',
        '//button[contains(text(), "Renew")]',
    ]
    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=10)
            sb.scroll_to(sel)
            human_sleep()
            sb.click(sel)
            log(f"✅ 点击成功: {sel}")
            return True
        except Exception:
            pass
    return False

# =========================
# Turnstile：被动等待（不解）
# =========================
def wait_cf_passive(sb, timeout=60):
    log("🛡️ 被动等待 Cloudflare 放行（不强求）")
    start = time.time()

    while time.time() - start < timeout:
        try:
            cookies = sb.get_cookies()
            if any(c["name"] == "cf_clearance" for c in cookies):
                log("✅ Cloudflare 已放行")
                return True
        except Exception:
            pass
        time.sleep(1)

    log("⚠️ Cloudflare 未放行，跳过续期流程")
    return False

# =========================
# NEXT / 다음
# =========================
def click_next_if_exists(sb):
    try:
        clicked = sb.execute_script("""
        (() => {
            for (const el of document.querySelectorAll("button, [role='button']")) {
                if (!el.offsetParent) continue;
                const t = (el.innerText || "").toLowerCase();
                if (t.includes("next") || t.includes("다음")) {
                    el.scrollIntoView({block:"center"});
                    el.click();
                    return true;
                }
            }
            return false;
        })();
        """)
        if clicked:
            log("✅ NEXT 已点击")
            return True
    except Exception:
        pass
    return False

# =========================
# 主流程
# =========================
def main():
    log("🚀 Weirdhost 自动续期（现实可落地版）")

    if not SERVER_URL:
        log("❌ WEIRDHOST_SERVER_URL 未设置，直接退出")
        return

    display = setup_xvfb()

    try:
        with SB(
            uc=True,
            headless=False,
            locale="en",
            chromium_arg=[
                "--window-size=1920,1080",
                "--disable-blink-features=AutomationControlled",
            ],
        ) as sb:

            # 首页
            sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", reconnect_time=5)
            wait_react_loaded(sb)

            # Cookie 登录
            if REMEMBER_WEB_COOKIE:
                log("🍪 注入 Cookie 登录")
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
            log(f"📦 打开服务器页面: {SERVER_URL}")
            sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=5)
            wait_react_loaded(sb)
            remove_ads(sb)
            human_scroll(sb)
            screenshot(sb, "01_server_page.png")

            # 点击时间追加
            if not click_time_add(sb):
                screenshot(sb, "renew_button_not_found.png")
                log("❌ 未找到续期按钮，结束")
                return

            screenshot(sb, "02_after_click.png")

            # 被动等 CF（不再死磕）
            if not wait_cf_passive(sb):
                screenshot(sb, "cf_blocked.png")
                return

            # 有 NEXT 就点，没有就算成功
            human_sleep(2, 4)
            click_next_if_exists(sb)
            human_sleep(5, 8)

            screenshot(sb, "03_done.png")
            log("🎉 Weirdhost 自动流程结束")

    finally:
        if display:
            display.stop()

if __name__ == "__main__":
    main()