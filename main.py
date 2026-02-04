import os
import time
import random
from seleniumbase import SB

# =========================
# 环境变量
# =========================
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

# =========================
# SOCKS5 代理
# =========================
SOCKS5_PROXY = "socks5://9afd1229:51e7ce204913@121.163.216.45:25525"

# =========================
# 截图目录
# =========================
os.makedirs("screenshots", exist_ok=True)


# =========================
# 工具函数
# =========================
def screenshot(sb, name):
    path = f"screenshots/{name}"
    try:
        sb.save_screenshot(path)
        print(f"📸 Screenshot saved: {path}")
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")


def human_sleep(a=0.8, b=2.0):
    time.sleep(random.uniform(a, b))


def wait_react_loaded(sb):
    sb.wait_for_ready_state_complete(timeout=30)
    human_sleep(1.5, 3.0)


def human_scroll(sb):
    try:
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.3)")
        human_sleep(1.2, 2.0)
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.65)")
        human_sleep(1.2, 2.0)
        sb.execute_script("window.scrollTo(0, 0)")
        human_sleep(1.0, 1.8)
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
# Renew / NEXT 逻辑
# =========================
def click_renew_button(sb):
    print("🕒 查找 Renew/시간 추가 按钮 ...")

    selectors = [
        'button[color="primary"]',
        'button:contains("시간 추가")',
        'button:contains("Renew")',
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
            pass

    try:
        clicked = sb.execute_script("""
        (() => {
            const keys = ["renew", "시간", "추가", "extend"];
            for (const b of document.querySelectorAll("button")) {
                const t = (b.innerText || "").toLowerCase();
                if (keys.some(k => t.includes(k))) {
                    b.scrollIntoView({block:"center"});
                    b.click();
                    return true;
                }
            }
            return false;
        })();
        """)
        if clicked:
            print("✅ JS fallback 点击成功")
            return True
    except Exception:
        pass

    return False


def wait_next_button(sb, timeout=60):
    print("⏳ 等待 NEXT 按钮出现 ...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            found = sb.execute_script("""
            (() => {
                return Array.from(document.querySelectorAll("button"))
                  .some(b => {
                    const t = (b.innerText || "").toLowerCase();
                    return b.offsetParent && (t.includes("next") || t.includes("다음"));
                  });
            })();
            """)
            if found:
                print("✅ NEXT 按钮已出现")
                return True
        except Exception:
            pass
        time.sleep(1)

    return False


def click_next_button(sb):
    print("🟢 尝试点击 NEXT ...")
    try:
        clicked = sb.execute_script("""
        (() => {
            for (const b of document.querySelectorAll("button")) {
                const t = (b.innerText || "").toLowerCase();
                if (b.offsetParent && (t.includes("next") || t.includes("다음"))) {
                    b.scrollIntoView({block:"center"});
                    b.click();
                    return true;
                }
            }
            return false;
        })();
        """)
        if clicked:
            print("✅ NEXT 点击成功")
            return True
    except Exception:
        pass
    return False


# =========================
# Turnstile 核心判断
# =========================
def wait_turnstile_passed(sb, timeout=90):
    print("🛡️ 等待 Turnstile 真正通过 ...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            passed = sb.execute_script("""
            (() => {
                const iframes = [...document.querySelectorAll("iframe")]
                  .filter(f => (f.src || "").includes("challenges.cloudflare.com"));
                if (iframes.length === 0) return true;
                for (const f of iframes) {
                    if (f.style.display === "none") return true;
                }
                return false;
            })();
            """)
            if passed:
                print("✅ Turnstile 判定通过")
                return True
        except Exception:
            pass
        time.sleep(1)

    print("❌ Turnstile 超时未通过")
    return False


# =========================
# 主流程
# =========================
def main():
    print("🚀 Weirdhost 自动续期启动")

    if not SERVER_URL:
        raise Exception("❌ WEIRDHOST_SERVER_URL 未设置")

    with SB(
        uc=True,
        locale="en",
        headless=False,
        chromium_arg=f"--window-size=1920,1080 --proxy-server={SOCKS5_PROXY}"
    ) as sb:

        print("🌐 启动浏览器 (UC + SOCKS5)")
        sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", reconnect_time=5)
        wait_react_loaded(sb)

        # Cookie 登录
        if REMEMBER_WEB_COOKIE:
            print("🍪 使用 Cookie 登录")
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

        print(f"📦 打开服务器页面: {SERVER_URL}")
        sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=5)
        wait_react_loaded(sb)

        remove_ads(sb)
        human_scroll(sb)
        screenshot(sb, "01_server_page.png")

        if not click_renew_button(sb):
            screenshot(sb, "renew_not_found.png")
            raise Exception("❌ Renew 按钮未找到")

        human_sleep(3, 5)
        screenshot(sb, "02_after_renew.png")

        # ===== Turnstile 真人方案 =====
        print("☑️ Cloudflare Turnstile 真人模式启动")

        human_scroll(sb)
        human_sleep(6, 10)

        for i in range(3):
            print(f"🧠 点击 Turnstile 第 {i+1} 次")
            try:
                sb.uc_gui_click_captcha()
            except Exception:
                pass

            human_sleep(4, 7)

            if wait_turnstile_passed(sb, timeout=30):
                break
        else:
            screenshot(sb, "cf_failed_final.png")
            raise Exception("❌ Turnstile 多次尝试仍失败")

        screenshot(sb, "03_turnstile_passed.png")

        if not wait_next_button(sb, timeout=60):
            screenshot(sb, "04_no_next.png")
            raise Exception("❌ NEXT 未出现")

        if not click_next_button(sb):
            screenshot(sb, "05_next_click_fail.png")
            raise Exception("❌ NEXT 点击失败")

        human_sleep(6, 10)
        screenshot(sb, "06_after_next.png")

        print("🔄 刷新确认续期状态")
        sb.refresh()
        wait_react_loaded(sb)
        screenshot(sb, "07_final.png")

        print("🎉 Weirdhost 自动续期完成")


if __name__ == "__main__":
    main()