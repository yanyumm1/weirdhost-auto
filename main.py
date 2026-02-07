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
# Xvfb 支持
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
# 点击 시간 추가
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
# ⭐ Turnstile 坐标点击核心
# =========================
def click_turnstile_checkbox(sb):
    rect = sb.execute_script("""
    const f = document.querySelector("iframe[src*='challenges.cloudflare.com']");
    if (!f) return null;

    // 修复样式
    f.style.display = "block";
    f.style.visibility = "visible";
    f.style.pointerEvents = "auto";

    const r = f.getBoundingClientRect();
    return {x:r.x, y:r.y, w:r.width, h:r.height};
    """)

    if not rect:
        return False

    # 中心点 + 随机偏移
    x = rect["x"] + rect["w"] * (0.45 + random.random()*0.1)
    y = rect["y"] + rect["h"] * (0.45 + random.random()*0.1)

    print(f"🖱️ Turnstile 点击坐标: {x:.1f}, {y:.1f}")

    try:
        sb.uc_gui_click_x_y(x, y)
        return True
    except Exception:
        return False

# =========================
# ⭐ Turnstile 通过检测
# =========================
def turnstile_passed(sb):
    try:
        cookies = sb.get_cookies()
        if any(c["name"] == "cf_clearance" for c in cookies):
            return True

        iframe_exist = sb.execute_script("""
        return document.querySelector("iframe[src*='challenges.cloudflare.com']") !== null;
        """)
        return not iframe_exist
    except Exception:
        return False

# =========================
# ⭐ Turnstile 主流程
# =========================
def solve_turnstile(sb, timeout=120):
    print("🛡️ 处理 Cloudflare Turnstile ...")
    start = time.time()
    attempt = 0

    while time.time() - start < timeout:
        attempt += 1

        if turnstile_passed(sb):
            print("✅ Turnstile 已通过")
            return True

        if click_turnstile_checkbox(sb):
            print(f"👉 已尝试点击 Turnstile ({attempt})")

        if attempt % 2 == 0:
            screenshot(sb, f"cf_attempt_{attempt}.png")

        human_sleep(2, 3)

    screenshot(sb, "cf_failed.png")
    return False

# =========================
# 主流程
# =========================
def main():
    print("🚀 Weirdhost 自动续期（强化 Turnstile 自动点击）")

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

            # 首页
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

            # 打开服务器
            print(f"📦 打开服务器页面: {SERVER_URL}")
            sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=5)
            wait_react_loaded(sb)
            remove_ads(sb)

            screenshot(sb, "01_server_page.png")

            # 点击时间追加
            if not click_time_add(sb):
                screenshot(sb, "renew_not_found.png")
                raise Exception("❌ 时间追加按钮未找到")

            screenshot(sb, "02_after_click.png")

            # 处理 Turnstile
            if not solve_turnstile(sb):
                raise Exception("❌ Turnstile 未通过")

            screenshot(sb, "03_turnstile_passed.png")

            human_sleep(5, 8)
            screenshot(sb, "04_done.png")

            print("🎉 Weirdhost 自动续期完成")

    finally:
        if display:
            display.stop()

if __name__ == "__main__":
    main()