import os
import time
from seleniumbase import SB

REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

os.makedirs("screenshots", exist_ok=True)


def screenshot(sb, name):
    try:
        path = f"screenshots/{name}"
        sb.save_screenshot(path)
        print(f"📸 Screenshot saved: {path}")
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")


def wait_react_loaded(sb, timeout=30):
    sb.wait_for_ready_state_complete(timeout=timeout)
    sb.sleep(2)


def remove_ads(sb):
    try:
        sb.execute_script("""
        (() => {
            document.querySelectorAll("iframe").forEach(f => f.remove());
        })();
        """)
    except Exception:
        pass


def click_renew_button(sb):
    print("🕒 查找 Renew/시간 추가 按钮 ...")

    selectors = [
        'button[color="primary"]',
        'button:contains("시간 추가")',
        'button:contains("Renew")',
        'button:contains("추가")',
        'div[class*="RenewBox"] button',
    ]

    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=10)
            sb.scroll_to(sel)
            sb.click(sel)
            print(f"✅ 点击成功: {sel}")
            return True
        except Exception:
            pass

    # JS fallback: scan all buttons
    try:
        clicked = sb.execute_script("""
        (() => {
            const btns = Array.from(document.querySelectorAll("button"));
            const keywords = ["renew", "extend", "add", "시간", "추가"];

            for (const b of btns) {
                const t = (b.innerText || "").trim().toLowerCase();
                if (!t) continue;

                for (const k of keywords) {
                    if (t.includes(k)) {
                        b.scrollIntoView({behavior:"instant", block:"center"});
                        b.click();
                        return true;
                    }
                }
            }
            return false;
        })();
        """)
        if clicked:
            print("✅ JS fallback 点击成功（按钮文本匹配）")
            return True
    except Exception as e:
        print("⚠️ JS fallback click failed:", e)

    print("❌ 未找到续期按钮")
    return False


def try_click_turnstile(sb):
    print("☑️ 尝试通过 Cloudflare Turnstile ...")
    try:
        sb.uc_gui_click_captcha()
        sb.sleep(4)
        print("✅ 已执行 uc_gui_click_captcha()")
        return True
    except Exception as e:
        print(f"⚠️ captcha 点击异常: {e}")
        return False


def get_turnstile_token(sb):
    """
    Turnstile token 可能存在于：
    - input[name="cf-turnstile-response"]
    - textarea[name="cf-turnstile-response"]
    - id="cf-chl-widget-xxxx_response"
    """
    try:
        token = sb.execute_script("""
        (() => {
            // 1) 标准 selector
            let el = document.querySelector('input[name="cf-turnstile-response"]')
                  || document.querySelector('textarea[name="cf-turnstile-response"]');

            if (el) {
                const v = (el.value || "").trim();
                if (v.length > 20) return v;
            }

            // 2) id 前缀匹配 cf-chl-widget-xxx_response
            const candidates = Array.from(document.querySelectorAll("input, textarea"))
                .filter(x => x.id && x.id.startsWith("cf-chl-widget-") && x.id.endsWith("_response"));

            for (const c of candidates) {
                const v = (c.value || "").trim();
                if (v.length > 20) return v;
            }

            return null;
        })();
        """)
        return token
    except Exception:
        return None


def wait_turnstile_token(sb, timeout=60):
    print("🧩 等待 Turnstile token ...")

    start = time.time()
    while time.time() - start < timeout:
        token = get_turnstile_token(sb)
        if token:
            print(f"✅ Turnstile token 已生成 (len={len(token)})")
            return token
        sb.sleep(1)

    print("❌ 超时：未获取 Turnstile token")
    return None


def wait_next_button(sb, timeout=30):
    """
    人工续期时，打勾后会弹出 NEXT modal
    所以我们等待 NEXT 出现
    """
    print("⏳ 等待 NEXT 按钮出现 ...")

    selectors = [
        'button:contains("NEXT")',
        'button:contains("Next")',
        'button:contains("next")',
        'button:contains("다음")',
    ]

    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=timeout)
            print(f"✅ 检测到 NEXT 按钮: {sel}")
            return sel
        except Exception:
            pass

    # JS fallback: scan all visible buttons
    try:
        found = sb.execute_script("""
        (() => {
            const btns = Array.from(document.querySelectorAll("button"))
                .filter(b => b.offsetParent !== null);

            for (const b of btns) {
                const t = (b.innerText || "").trim().toLowerCase();
                if (t.includes("next") || t.includes("다음")) {
                    return true;
                }
            }
            return false;
        })();
        """)
        if found:
            print("✅ JS fallback 检测到 NEXT 按钮")
            return "JS_FOUND"
    except Exception:
        pass

    print("❌ 未检测到 NEXT 按钮")
    return None


def click_next_button(sb):
    print("🟢 尝试点击 NEXT ...")

    selectors = [
        'button:contains("NEXT")',
        'button:contains("Next")',
        'button:contains("next")',
        'button:contains("다음")',
    ]

    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=5)
            sb.scroll_to(sel)
            sb.click(sel)
            print(f"✅ 点击 NEXT 成功: {sel}")
            return True
        except Exception:
            pass

    # JS fallback click
    try:
        clicked = sb.execute_script("""
        (() => {
            const btns = Array.from(document.querySelectorAll("button"))
                .filter(b => b.offsetParent !== null);

            for (const b of btns) {
                const t = (b.innerText || "").trim().toLowerCase();
                if (t.includes("next") || t.includes("다음")) {
                    b.scrollIntoView({behavior:"instant", block:"center"});
                    b.click();
                    return true;
                }
            }
            return false;
        })();
        """)
        if clicked:
            print("✅ JS fallback 点击 NEXT 成功")
            return True
    except Exception as e:
        print("⚠️ JS fallback NEXT click failed:", e)

    print("❌ NEXT 点击失败")
    return False


def main():
    print("=== Weirdhost 自动续期启动 ===")

    if not SERVER_URL:
        raise Exception("❌ WEIRDHOST_SERVER_URL 未设置")

    with SB(
        uc=True,
        locale="en",
        test=True,
        headless=False,
        chromium_arg="--window-size=1920,1080"
    ) as sb:

        print("🚀 浏览器启动")

        sb.open("https://hub.weirdhost.xyz")
        wait_react_loaded(sb)

        # ---------- Cookie 登录 ----------
        if REMEMBER_WEB_COOKIE:
            print("🔐 Cookie 登录 (remember_web...)")

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

        # ---------- 打开服务器 ----------
        print(f"🌐 打开服务器页面: {SERVER_URL}")
        sb.open(SERVER_URL)
        wait_react_loaded(sb)
        remove_ads(sb)

        screenshot(sb, "01_server_page.png")

        # ---------- 点击续期 ----------
        if not click_renew_button(sb):
            screenshot(sb, "02_renew_not_found.png")
            raise Exception("❌ 未找到续期按钮")

        sb.sleep(2)
        screenshot(sb, "03_after_click_renew.png")

        # ---------- Turnstile ----------
        try_click_turnstile(sb)
        screenshot(sb, "04_after_turnstile_click.png")

        # ---------- 等 token ----------
        token = wait_turnstile_token(sb, timeout=60)
        if not token:
            screenshot(sb, "05_no_turnstile_token.png")
            raise Exception("❌ 未获取 Turnstile token（验证码未通过）")

        screenshot(sb, "06_turnstile_token_ready.png")

        # ---------- 等 NEXT ----------
        wait_next_button(sb, timeout=30)
        screenshot(sb, "07_next_visible.png")

        # ---------- 点击 NEXT ----------
        if not click_next_button(sb):
            screenshot(sb, "08_next_click_failed.png")
            raise Exception("❌ NEXT 点击失败")

        print("⏳ 等待续期完成 ...")
        sb.sleep(6)

        screenshot(sb, "09_after_next.png")

        # ---------- 刷新确认 ----------
        print("🔄 刷新页面确认状态更新 ...")
        sb.refresh()
        wait_react_loaded(sb)
        remove_ads(sb)

        screenshot(sb, "10_after_refresh.png")

        print("=== 任务完成 ===")
        print("✅ 已执行 Turnstile + NEXT（请核对截图确认续期是否生效）")


if __name__ == "__main__":
    main()