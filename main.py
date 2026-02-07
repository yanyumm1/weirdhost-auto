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
# Cloudflare 检测
# =========================
def is_cloudflare_page(sb):
    try:
        html = sb.get_page_source().lower()
        keywords = [
            "verify you are human",
            "verifying",
            "just a moment",
            "checking your browser",
            "cf-browser-verification",
            "challenge-platform",
            "challenges.cloudflare.com",
            "turnstile",
            "__cf_chl",
            "cloudflare",
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


def print_cookies(sb):
    try:
        cookies = sb.get_cookies()
        print(f"🍪 当前 Cookie 数量: {len(cookies)}")
        for c in cookies:
            if c.get("name") in ["cf_clearance", "__cf_bm"]:
                print(f"   {c.get('name')}: {c.get('value')[:60]}...")
    except Exception:
        pass


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
# Cloudflare / Turnstile 处理（强化版）
# =========================
def solve_cloudflare(sb, timeout=180):
    """
    强化 Cloudflare 绕过逻辑:
    - 优先用 uc_gui_click_captcha()
    - 反复 refresh + 等待
    - 必须拿到 cf_clearance 才算成功
    """
    print("🛡️ 开始处理 Cloudflare / Turnstile ...")

    start = time.time()
    attempt = 0

    while time.time() - start < timeout:
        attempt += 1

        if has_cf_clearance(sb):
            print("✅ Cloudflare 已通过 (检测到 cf_clearance)")
            return True

        if not is_cloudflare_page(sb):
            print("ℹ️ 当前页面不像 Cloudflare 验证页，但仍等待 clearance ...")
            time.sleep(2)

            if has_cf_clearance(sb):
                print("✅ Cloudflare 已通过 (页面正常 + cookie 已写入)")
                return True

        print(f"🔁 Cloudflare 处理尝试 {attempt}")

        # 截图记录
        if attempt % 2 == 0:
            screenshot(sb, f"cf_attempt_{attempt}.png")

        # 尝试 SeleniumBase 内置点击
        try:
            print("🖱️ 尝试 uc_gui_click_captcha() ...")
            sb.uc_gui_click_captcha(frame="iframe", retry=False, blind=False)
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ uc_gui_click_captcha 失败: {e}")

        # 等待验证
        print("⏳ 等待 Cloudflare 验证中 ...")
        time.sleep(6)

        # 检查 cookie
        if has_cf_clearance(sb):
            print("✅ Cloudflare 已通过 (captcha 后写入 clearance)")
            return True

        # 每 3 次 refresh 一次（Cloudflare 很吃这个）
        if attempt % 3 == 0:
            print("🔄 refresh 页面触发 Cloudflare 放行 ...")
            try:
                sb.refresh()
                wait_react_loaded(sb)
            except Exception:
                pass

        # 每 5 次重连打开一次（更激进）
        if attempt % 5 == 0:
            try:
                url = sb.get_current_url()
                print(f"🔌 reconnect open: {url}")
                sb.uc_open_with_reconnect(url, reconnect_time=4)
                wait_react_loaded(sb)
            except Exception:
                pass

        human_sleep(2, 4)

    screenshot(sb, "cf_failed.png")
    return False


# =========================
# 主流程
# =========================
def main():
    print("🚀 Weirdhost 自动续期（GitHub Actions + Cloudflare 强化版）")

    if not SERVER_URL:
        raise Exception("❌ WEIRDHOST_SERVER_URL 未设置")

    display = setup_xvfb()

    try:
        with SB(
            uc=True,
            headless=False,   # GitHub Actions 建议 False + Xvfb
            locale="en",
            chromium_arg="--no-sandbox --disable-blink-features=AutomationControlled --window-size=1920,1080"
        ) as sb:

            # 先打开首页
            sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", reconnect_time=5)
            wait_react_loaded(sb)

            # 注入 Cookie 登录
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

            screenshot(sb, "00_home.png")

            # 打开服务器页面
            print(f"📦 打开服务器页面: {SERVER_URL}")
            sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=5)
            wait_react_loaded(sb)
            remove_ads(sb)

            screenshot(sb, "01_server_page.png")

            # 点击续期按钮
            if not click_time_add(sb):
                screenshot(sb, "renew_not_found.png")
                raise Exception("❌ 时间追加按钮未找到")

            screenshot(sb, "02_after_click.png")

            # 如果触发 Cloudflare，开始处理
            if is_cloudflare_page(sb) or not has_cf_clearance(sb):
                print("⚠️ 检测到可能存在 Cloudflare 验证，开始绕过...")
                if not solve_cloudflare(sb, timeout=240):
                    print_cookies(sb)
                    raise Exception("❌ Cloudflare / Turnstile 未通过")

            screenshot(sb, "03_cf_passed.png")

            # 最终等待页面稳定
            human_sleep(6, 10)

            # 最终验证
            if is_cloudflare_page(sb) and not has_cf_clearance(sb):
                screenshot(sb, "04_still_verify.png")
                raise Exception("❌ 最终仍停留在 Verify you are human")

            screenshot(sb, "04_done.png")

            print_cookies(sb)
            print("🎉 Weirdhost 自动续期完成")

    finally:
        if display:
            display.stop()


if __name__ == "__main__":
    main()