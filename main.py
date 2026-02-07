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

def human_sleep(a=1.0, b=2.5):
    time.sleep(random.uniform(a, b))

def wait_react_loaded(sb):
    sb.wait_for_ready_state_complete(timeout=30)
    human_sleep(2, 3)

def human_scroll(sb):
    try:
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.3)")
        human_sleep(1.5, 2.5)
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6)")
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
# CF 判断
# =========================
def cf_cookie_present(sb):
    try:
        cookies = sb.get_cookies()
        return any(
            c["name"] in ("cf_clearance", "__cf_bm")
            for c in cookies
        )
    except Exception:
        return False

def wait_turnstile_passed(sb, timeout=90):
    print("🛡️ 等待 Turnstile 通过判定 ...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            # ① Cookie 已下发，直接判定通过
            if cf_cookie_present(sb):
                print("✅ CF Cookie 已存在")
                return True

            # ② iframe 消失或被隐藏
            iframe_ok = sb.execute_script("""
            (() => {
                const iframes = [...document.querySelectorAll("iframe")]
                  .filter(f => (f.src || "").includes("challenges.cloudflare.com"));
                if (iframes.length === 0) return true;
                return iframes.some(f => f.style.display === "none");
            })();
            """)
            if iframe_ok:
                print("✅ Turnstile iframe 已释放")
                return True
        except Exception:
            pass

        time.sleep(1)

    print("❌ Turnstile 超时未通过")
    return False

# =========================
# Renew / NEXT
# =========================
def click_renew_button(sb):
    print("🕒 查找 Renew 按钮 ...")
    try:
        clicked = sb.execute_script("""
        (() => {
            const keys = ["renew", "시간", "추가", "extend"];
            for (const b of document.querySelectorAll("button")) {
                const t = (b.innerText || "").toLowerCase();
                if (keys.some(k => t.includes(k)) && b.offsetParent) {
                    b.scrollIntoView({block:"center"});
                    b.click();
                    return true;
                }
            }
            return false;
        })();
        """)
        return bool(clicked)
    except Exception:
        return False

def wait_next_button(sb, timeout=60):
    print("⏳ 等待 NEXT 按钮 ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            found = sb.execute_script("""
            (() => {
                return [...document.querySelectorAll("button")]
                  .some(b => {
                    const t = (b.innerText || "").toLowerCase();
                    return b.offsetParent && (t.includes("next") || t.includes("다음"));
                  });
            })();
            """)
            if found:
                print("✅ NEXT 出现")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def click_next_button(sb):
    try:
        return sb.execute_script("""
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
    except Exception:
        return False

# =========================
# 主流程
# =========================
def main():
    print("🚀 Weirdhost 自动续期启动（方案 B）")

    if not SERVER_URL:
        raise Exception("❌ WEIRDHOST_SERVER_URL 未设置")

    with SB(
        uc=True,
        locale="en",
        headless=False,
        chromium_arg="--window-size=1920,1080"
    ) as sb:

        print("🌐 打开 Weirdhost")
        sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", reconnect_time=5)
        wait_react_loaded(sb)

        if REMEMBER_WEB_COOKIE:
            print("🍪 注入 Cookie")
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
            raise Exception("❌ Renew 未找到")

        screenshot(sb, "02_after_renew.png")

        # ===== Turnstile 真人节奏 =====
        print("🧍 静置等待 CF 风控评估（非常关键）")
        human_sleep(20, 30)

        human_scroll(sb)
        human_sleep(8, 12)

        print("🖱️ 尝试一次 Turnstile 点击")
        try:
            sb.uc_gui_click_captcha()
        except Exception:
            pass

        if not wait_turnstile_passed(sb, timeout=90):
            screenshot(sb, "cf_failed.png")
            raise Exception("❌ Turnstile 未通过")

        screenshot(sb, "03_turnstile_passed.png")

        if not wait_next_button(sb):
            screenshot(sb, "no_next.png")
            raise Exception("❌ NEXT 未出现")

        if not click_next_button(sb):
            screenshot(sb, "next_click_fail.png")
            raise Exception("❌ NEXT 点击失败")

        human_sleep(6, 10)
        screenshot(sb, "04_done.png")

        print("🎉 Weirdhost 自动续期完成")

if __name__ == "__main__":
    main()