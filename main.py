import os
import time
import random
from pathlib import Path
from seleniumbase import SB


# ============================================================
# 必须保留：环境变量读取
# ============================================================
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

# 你提供的 socks5
SOCKS5_PROXY = os.environ.get(
    "SOCKS5_PROXY",
    "socks5://9afd1229:51e7ce204913@121.163.216.45:25525"
)

SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 工具函数
# ============================================================
def save_shot(sb, name: str):
    path = SCREENSHOT_DIR / name
    sb.save_screenshot(str(path))
    print(f"📸 Screenshot saved: {path}")


def human_sleep(a=0.4, b=1.5):
    time.sleep(random.uniform(a, b))


def human_scroll(sb):
    """随机滚动，模拟人类行为"""
    try:
        scroll_y = random.randint(200, 900)
        sb.execute_script(f"window.scrollBy(0, {scroll_y});")
        human_sleep(0.4, 1.2)
        sb.execute_script(f"window.scrollBy(0, {-random.randint(50, 250)});")
        human_sleep(0.3, 1.0)
    except Exception:
        pass


def random_click_blank(sb):
    """随机点击空白区域，触发 Turnstile 行为检测"""
    try:
        sb.execute_script("""
            document.body.dispatchEvent(new MouseEvent('mousemove', {clientX: 200, clientY: 200}));
        """)
        human_sleep(0.2, 0.6)

        sb.click("body")
        human_sleep(0.3, 1.0)
    except Exception:
        pass


def cookie_login(sb):
    """
    通过 remember_web cookie 登录
    """
    if not REMEMBER_WEB_COOKIE:
        raise Exception("❌ 缺少环境变量 REMEMBER_WEB_COOKIE")

    print("🔐 Cookie 登录 (remember_web...)")

    sb.open("https://weirdhost.xyz/")
    human_sleep(1, 2)

    sb.add_cookie({
        "name": "remember_web",
        "value": REMEMBER_WEB_COOKIE,
        "domain": ".weirdhost.xyz",
        "path": "/"
    })

    human_sleep(0.5, 1.0)


def click_renew_button(sb) -> bool:
    """
    点击 Renew / 시간 추가
    """
    print("🕒 查找 Renew/시간 추가 按钮 ...")

    selectors = [
        'button[color="primary"]',
        'button:contains("Renew")',
        'button:contains("시간 추가")',
        'button:contains("추가")',
    ]

    for sel in selectors:
        try:
            if sb.is_element_visible(sel):
                sb.click(sel)
                print(f"✅ 点击成功: {sel}")
                return True
        except Exception:
            continue

    return False


def detect_turnstile_present(sb) -> bool:
    """
    判断页面是否有 Turnstile
    """
    try:
        html = sb.get_page_source().lower()
        if "turnstile" in html or "challenges.cloudflare" in html:
            return True
    except Exception:
        pass

    # iframe 方式检测
    try:
        iframes = sb.find_elements("iframe")
        for f in iframes:
            try:
                src = f.get_attribute("src") or ""
                if "turnstile" in src or "cloudflare" in src:
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def try_click_turnstile(sb) -> bool:
    """
    重点函数：
    尝试通过 Turnstile（不等 token、不等 next）
    只做：拟人化 + 点击 captcha
    """
    print("☑️ 尝试通过 Cloudflare Turnstile ...")

    # 先滚动和随机点击，增加人类特征
    human_scroll(sb)
    random_click_blank(sb)

    # SeleniumBase UC 内置验证码点击
    try:
        sb.uc_gui_click_captcha()
        print("✅ 已执行 uc_gui_click_captcha()")
        return True
    except Exception as e:
        print(f"⚠️ uc_gui_click_captcha() 执行失败: {e}")
        return False


def detect_renew_success(sb) -> bool:
    """
    检测是否续期成功（不依赖 Turnstile token）
    只靠页面变化判断
    """
    try:
        html = sb.get_page_source().lower()

        success_keywords = [
            "success",
            "renewed",
            "completed",
            "done",
            "연장",
            "성공",
            "갱신",
            "updated",
            "expires",
            "expiration",
        ]

        for k in success_keywords:
            if k in html:
                return True
    except Exception:
        pass

    # 如果 Turnstile 已消失，也很可能成功
    if not detect_turnstile_present(sb):
        return True

    return False


def wait_for_renew_result(sb, timeout=30) -> bool:
    """
    等待续期结果出现
    """
    start = time.time()
    while time.time() - start < timeout:
        human_sleep(1.0, 2.0)

        # 页面可能会自动刷新或弹窗
        try:
            if detect_renew_success(sb):
                return True
        except Exception:
            pass

    return False


def ensure_page_loaded(sb):
    """等待页面加载稳定"""
    human_sleep(1.5, 2.8)
    try:
        sb.wait_for_ready_state_complete(timeout=10)
    except Exception:
        pass


# ============================================================
# 主流程
# ============================================================
def main():
    print("\n=== Weirdhost 自动续期启动 ===\n")

    if not SERVER_URL:
        raise Exception("❌ 缺少环境变量 WEIRDHOST_SERVER_URL")

    print("🚀 浏览器启动 (UC Mode + SOCKS5 Proxy)")
    print(f"🌍 Proxy: {SOCKS5_PROXY}")

    with SB(
        uc=True,
        test=True,
        locale="en",
        headless=False,          # 必须 false，提高通过率
        proxy=SOCKS5_PROXY,
        chromium_arg="--disable-blink-features=AutomationControlled",
    ) as sb:

        # 1) Cookie 登录
        cookie_login(sb)

        # 2) 打开服务器页面
        print(f"🌐 打开服务器页面: {SERVER_URL}")
        sb.open(SERVER_URL)
        ensure_page_loaded(sb)
        save_shot(sb, "01_server_page.png")

        # 3) 点击 Renew
        if not click_renew_button(sb):
            save_shot(sb, "02_no_renew_button.png")
            raise Exception("❌ 未找到 Renew/시간 추가 按钮")

        ensure_page_loaded(sb)
        save_shot(sb, "03_after_click_renew.png")

        # 4) 如果有 Turnstile，就尝试多轮拟人化点击
        max_try = 6
        for i in range(max_try):
            print(f"\n🧩 Turnstile 处理轮次: {i+1}/{max_try}")

            if not detect_turnstile_present(sb):
                print("✅ 未检测到 Turnstile（可能已经通过或不需要验证）")
                break

            try_click_turnstile(sb)
            human_sleep(2.5, 4.5)

            # 有时候需要滚动触发
            human_scroll(sb)
            human_sleep(0.8, 1.6)

            # 检测是否成功
            if detect_renew_success(sb):
                print("✅ 检测到续期成功迹象")
                break

            # 有时候 Turnstile 点击后页面需要刷新一次才生效
            if i in (1, 3):
                print("🔄 尝试刷新页面触发验证完成...")
                sb.refresh()
                ensure_page_loaded(sb)

        save_shot(sb, "04_after_turnstile_process.png")

        # 5) 等待续期结果（不再等 token、不再等 NEXT）
        print("\n⏳ 等待续期结果确认 ...")
        ok = wait_for_renew_result(sb, timeout=35)

        if ok:
            print("🎉 续期成功（检测到页面已通过/续期成功标记）")
            save_shot(sb, "05_renew_success.png")
        else:
            print("❌ 未检测到续期成功标记（可能仍未通过 Turnstile）")
            save_shot(sb, "05_renew_failed.png")
            raise Exception("❌ 自动续期失败：Turnstile 未通过或页面无成功标记")


if __name__ == "__main__":
    main()