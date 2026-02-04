import os
import time
from seleniumbase import SB

REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

os.makedirs("screenshots", exist_ok=True)


def screenshot(sb, name):
    path = f"screenshots/{name}"
    sb.save_screenshot(path)
    print(f"📸 Screenshot saved: {path}")


def wait_react_loaded(sb, timeout=30):
    sb.wait_for_ready_state_complete(timeout=timeout)
    sb.sleep(2)


def remove_ads(sb):
    try:
        sb.execute_script("""
        document.querySelectorAll("iframe").forEach(f=>f.remove());
        """)
    except Exception:
        pass


def click_renew_button(sb):
    print("🕒 查找 Renew/시간 추가 按钮 ...")

    selectors = [
        'button[color="primary"]',
        'button:contains("Renew")',
        'button:contains("시간 추가")',
        'button:contains("추가")',
        'div[class*="RenewBox"] button',
    ]

    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=8)
            sb.scroll_to(sel)
            sb.click(sel)
            print(f"✅ 点击成功: {sel}")
            return True
        except Exception:
            pass

    # JS fallback: scan all buttons
    try:
        clicked = sb.execute_script("""
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
        """)
        if clicked:
            print("✅ JS fallback 点击成功（按钮文本匹配）")
            return True
    except Exception:
        pass

    print("❌ 未找到 Renew 按钮")
    return False


def wait_turnstile_token(sb, timeout=40):
    """
    Weirdhost 使用 Turnstile token，不会给 cf_clearance cookie。
    所以我们等 hidden input: name="cf-turnstile-response"
    """
    print("🧩 等待 Turnstile token (cf-turnstile-response) ...")

    start = time.time()
    while time.time() - start < timeout:
        token = sb.execute_script("""
        const el = document.querySelector('input[name="cf-turnstile-response"]');
        if (!el) return null;
        const v = (el.value || "").trim();
        return v.length > 10 ? v : null;
        """)
        if token:
            print(f"✅ Turnstile token 已生成 (len={len(token)})")
            return token

        sb.sleep(1)

    print("❌ 超时：未获取 Turnstile token")
    return None


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


def click_confirm_button(sb):
    """
    Renew modal 里通常会有第二个确认按钮，比如：
    Confirm / Submit / Renew / 추가 / 결제 등
    """
    print("🟢 尝试点击确认续期按钮 ...")

    selectors = [
        'button:contains("Confirm")',
        'button:contains("Submit")',
        'button:contains("Renew")',
        'button:contains("Pay")',
        'button:contains("Continue")',
        'button:contains("확인")',
        'button:contains("결제")',
        'button:contains("추가")',
        'button[type="submit"]',
    ]

    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=5)
            sb.scroll_to(sel)
            sb.click(sel)
            print(f"✅ 点击确认按钮成功: {sel}")
            return True
        except Exception:
            pass

    # JS fallback: click last visible button in dialog/modal
    try:
        clicked = sb.execute_script("""
        const dialog = document.querySelector('div[role="dialog"]') ||
                       document.querySelector("#renew-modal") ||
                       document.querySelector(".MuiDialog-root");

        const scope = dialog || document;

        const btns = Array.from(scope.querySelectorAll("button"))
            .filter(b => b.offsetParent !== null);

        if (btns.length === 0) return false;

        // 常见：最后一个是 confirm
        const last = btns[btns.length - 1];
        last.scrollIntoView({behavior:"instant", block:"center"});
        last.click();
        return true;
        """)
        if clicked:
            print("✅ JS fallback 点击确认按钮成功")
            return True
    except Exception:
        pass

    print("⚠️ 未找到确认按钮")
    return False


def submit_form_fallback(sb):
    """
    如果站点确实是 form submit 驱动（虽然你说人工不用 submit，但这里做兜底）
    """
    print("📨 fallback: 尝试 form.submit() ...")
    try:
        sb.execute_script("""
        const form =
            document.querySelector('#renew-modal form') ||
            document.querySelector('form');

        if (form) form.submit();
        """)
        print("✅ 已执行 form.submit()")
        return True
    except Exception as e:
        print("❌ form.submit() 失败:", e)
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

        # 打开 hub 首页
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
            raise Exception("❌ 未找到 Renew 按钮")

        sb.sleep(2)
        screenshot(sb, "03_after_click_renew.png")

        # ---------- Turnstile ----------
        try_click_turnstile(sb)
        screenshot(sb, "04_after_turnstile_click.png")

        # ---------- 等 token ----------
        token = wait_turnstile_token(sb, timeout=50)
        if not token:
            screenshot(sb, "05_no_turnstile_token.png")
            raise Exception("❌ 未获取 cf-turnstile-response token（验证未通过）")

        screenshot(sb, "06_turnstile_token_ready.png")

        # ---------- 点击确认/续期 ----------
        clicked = click_confirm_button(sb)
        if not clicked:
            print("⚠️ 未找到确认按钮，尝试 fallback submit")
            submit_form_fallback(sb)

        # ---------- 等待页面处理 ----------
        print("⏳ 等待续期请求完成 ...")
        sb.sleep(6)

        screenshot(sb, "07_after_submit.png")

        # ---------- 刷新确认 ----------
        print("🔄 刷新页面确认状态更新 ...")
        sb.refresh()
        wait_react_loaded(sb)
        remove_ads(sb)

        screenshot(sb, "08_after_refresh.png")

        print("=== 任务完成 ===")
        print("✅ 已完成 Turnstile + 提交动作（请核对截图确认续期是否生效）")


if __name__ == "__main__":
    main()