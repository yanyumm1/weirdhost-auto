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
    try:
        sb.wait_for_ready_state_complete(timeout=30)
    except Exception:
        pass
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
        '//button[contains(text(), "시간 추가")]',
        '//button[contains(text(), "Renew")]',
        '//button[contains(text(), "renew")]',
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
# 检测 Cloudflare 页面状态
# =========================
def page_has_cloudflare_text(sb):
    try:
        html = sb.get_page_source().lower()
        keywords = [
            "verify you are human",
            "verifying",
            "cloudflare",
            "cf-browser-verification",
            "challenge-platform",
            "turnstile",
        ]
        return any(k in html for k in keywords)
    except Exception:
        return False

def has_cf_clearance(sb):
    try:
        cookies = sb.get_cookies()
        for c in cookies:
            if c.get("name") == "cf_clearance" and c.get("value"):
                return True
        return False
    except Exception:
        return False

# =========================
# Turnstile 坐标点击
# =========================
def click_turnstile_checkbox(sb):
    rect = sb.execute_script("""
    const f = document.querySelector("iframe[src*='challenges.cloudflare.com']");
    if (!f) return null;

    f.style.display = "block";
    f.style.visibility = "visible";
    f.style.pointerEvents = "auto";

    const r = f.getBoundingClientRect();
    return {x:r.x, y:r.y, w:r.width, h:r.height};
    """)

    if not rect:
        print("⚠️ 未找到 Turnstile iframe")
        return False

    # 中心点 + 随机偏移
    x = rect["x"] + rect["w"] * (0.40 + random.random() * 0.2)
    y = rect["y"] + rect["h"] * (0.40 + random.random() * 0.2)

    print(f"🖱️ Turnstile 点击坐标: {x:.1f}, {y:.1f}")

    try:
        sb.uc_gui_click_x_y(x, y)
        return True
    except Exception as e:
        print(f"⚠️ Turnstile 点击失败: {e}")
        return False

# =========================
# 等待 Cloudflare verifying 结束
# =========================
def wait_cloudflare_verifying(sb, timeout=40):
    print("⏳ 等待 Cloudflare Verifying 结束 ...")
    start = time.time()

    while time.time() - start < timeout:
        if has_cf_clearance(sb):
            print("✅ 检测到 cf_clearance cookie")
            return True

        if not page_has_cloudflare_text(sb):
            # 页面已经不像验证页了
            return True

        time.sleep(2)

    return False

# =========================
# Turnstile 主流程（修复版）
# =========================
def solve_turnstile(sb, timeout=180):
    print("🛡️ 处理 Cloudflare Turnstile ...")
    start = time.time()
    attempt = 0

    while time.time() - start < timeout:
        attempt += 1

        # 真正通过条件：cf_clearance
        if has_cf_clearance(sb):
            print("✅ Turnstile 已通过 (cf_clearance)")
            return True

        # 如果页面已经不是验证页，也可以认为通过（但仍建议等 cookie）
        if not page_has_cloudflare_text(sb):
            print("ℹ️ 页面不再显示 Cloudflare 验证内容，继续确认 cookie ...")
            time.sleep(2)

        print(f"🔁 Turnstile 尝试次数: {attempt}")

        # 点击 checkbox
        clicked = click_turnstile_checkbox(sb)
        if clicked:
            print("👉 已尝试点击 Turnstile")

        # 等待 verifying
        wait_cloudflare_verifying(sb, timeout=25)

        # 再次检查 cookie
        if has_cf_clearance(sb):
            print("✅ Turnstile 已通过 (after wait)")
            return True

        # 偶数次截图
        if attempt % 2 == 0:
            screenshot(sb, f"cf_attempt_{attempt}.png")

        # 某些情况下刷新会触发 cookie 写入
        if attempt % 3 == 0:
            print("🔄 尝试刷新页面触发 Cloudflare 放行 ...")
            try:
                sb.refresh()
                wait_react_loaded(sb)
            except Exception:
                pass

        human_sleep(3, 5)

    screenshot(sb, "cf_failed.png")
    return False

# =========================
# 主流程
# =========================
def main():
    print("🚀 Weirdhost 自动续期（UC + 强化 Turnstile 自动点击 修复版）")

    if not SERVER_URL:
        raise Exception("❌ WEIRDHOST_SERVER_URL 未设置")

    display = setup_xvfb()

    try:
        with SB(
            uc=True,
            headless=False,
            locale="en",
            chromium_arg="--no-sandbox --disable-blink-features=AutomationControlled --window-size=1920,1080"
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

            # 处理 Turnstile（修复版）
            if not solve_turnstile(sb):
                raise Exception("❌ Turnstile 未通过")

            screenshot(sb, "03_turnstile_passed.png")

            # 等待页面完全加载/跳转
            human_sleep(6, 10)

            # 最终确认页面不是 verify
            if page_has_cloudflare_text(sb) and not has_cf_clearance(sb):
                screenshot(sb, "04_still_verify.png")
                raise Exception("❌ 仍停留在 Verify you are human，Cloudflare 未真正放行")

            screenshot(sb, "04_done.png")
            print("🎉 Weirdhost 自动续期完成")

    finally:
        if display:
            display.stop()

if __name__ == "__main__":
    main()