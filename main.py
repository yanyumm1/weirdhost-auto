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
# Cloudflare 判断
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
    print("🛡️ 等待 Turnstile 放行 ...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            if cf_cookie_present(sb):
                print("✅ CF Cookie 已存在")
                return True

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

    print("❌ Turnstile 超时")
    return False

# =========================
# Renew / NEXT
# =========================
def click_renew_button(sb):
    print("🕒 查找 Renew / 시간 추가 按钮 ...")

    try:
        clicked = sb.execute_script("""
        (() => {
            const KEYWORDS = ["renew", "extend", "시간", "추가"];

            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode(node) {
                        const t = node.textContent?.trim();
                        if (!t) return NodeFilter.FILTER_REJECT;
                        return KEYWORDS.some(k => t.toLowerCase().includes(k))
                            ? NodeFilter.FILTER_ACCEPT
                            : NodeFilter.FILTER_REJECT;
                    }
                }
            );

            let node;
            while ((node = walker.nextNode())) {
                let el = node.parentElement;

                for (let i = 0; i < 6 && el; i++) {
                    const tag = el.tagName?.toLowerCase();
                    const role = el.getAttribute?.("role");

                    const clickable =
                        tag === "button" ||
                        role === "button" ||
                        el.onclick ||
                        el.tabIndex >= 0;

                    if (clickable && el.offsetParent) {
                        el.scrollIntoView({ block: "center", behavior: "smooth" });
                        el.click();
                        return true;
                    }
                    el = el.parentElement;
                }
            }
            return false;
        })();
        """)

        if clicked:
            print("✅ 已点击 Renew / 시간 추가")
            return True
    except Exception as e:
        print("⚠️ Renew JS 异常:", e)

    return False

def wait_next_button(sb, timeout=60):
    print("⏳ 等待 NEXT / 다음 按钮 ...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            found = sb.execute_script("""
            (() => {
                return [...document.querySelectorAll("button, [role='button']")]
                  .some(el => {
                    const t = (el.innerText || "").toLowerCase();
                    return el.offsetParent && (t.includes("next") || t.includes("다음"));
                  });
            })();
            """)
            if found:
                print("✅ NEXT 已出现")
                return True
        except Exception:
            pass
        time.sleep(1)

    return False

def click_next_button(sb):
    try:
        clicked = sb.execute_script("""
        (() => {
            for (const el of document.querySelectorAll("button, [role='button']")) {
                const t = (el.innerText || "").toLowerCase();
                if (el.offsetParent && (t.includes("next") || t.includes("다음"))) {
                    el.scrollIntoView({ block: "center" });
                    el.click();
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
# 主流程
# =========================
def main():
    print("🚀 Weirdhost 自动续期启动（方案 B 完整版）")

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

        print(f"📦 打开服务器页面: {SERVER_URL}")
        sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=5)
        wait_react_loaded(sb)

        remove_ads(sb)
        human_scroll(sb)
        screenshot(sb, "01_server_page.png")

        if not click_renew_button(sb):
            screenshot(sb, "renew_not_found.png")
            raise Exception("❌ Renew / 시간 추가 未找到")

        screenshot(sb, "02_after_renew.png")

        # ===== Turnstile 真人节奏 =====
        print("🧍 静置等待 CF 风控评估")
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
            raise Exception("❌ NEXT / 다음 未出现")

        if not click_next_button(sb):
            screenshot(sb, "next_click_fail.png")
            raise Exception("❌ NEXT 点击失败")

        human_sleep(6, 10)
        screenshot(sb, "04_done.png")

        print("🎉 Weirdhost 自动续期完成")

if __name__ == "__main__":
    main()