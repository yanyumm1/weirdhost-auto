import os
import time
import random
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


def human_sleep(a=0.6, b=1.8):
    time.sleep(random.uniform(a, b))


def wait_react_loaded(sb, timeout=30):
    sb.wait_for_ready_state_complete(timeout=timeout)
    human_sleep(1.2, 2.5)


def remove_ads(sb):
    try:
        sb.execute_script("""
        (() => {
            document.querySelectorAll("iframe").forEach(f => {
                if (!String(f.src || "").includes("challenges.cloudflare.com")) {
                    f.remove();
                }
            });
        })();
        """)
    except Exception:
        pass


def human_like_scroll(sb):
    try:
        sb.execute_script("""
        (() => {
            window.scrollTo(0, Math.floor(document.body.scrollHeight * 0.2));
        })();
        """)
        human_sleep()

        sb.execute_script("""
        (() => {
            window.scrollTo(0, Math.floor(document.body.scrollHeight * 0.5));
        })();
        """)
        human_sleep()

        sb.execute_script("""
        (() => {
            window.scrollTo(0, 0);
        })();
        """)
        human_sleep()
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
            sb.wait_for_element_visible(sel, timeout=12)
            sb.scroll_to(sel)
            human_sleep()
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


def wait_for_turnstile_iframe(sb, timeout=25):
    """
    Turnstile 通常在 challenges.cloudflare.com iframe 里
    """
    print("🧱 等待 Turnstile iframe 加载 ...")

    start = time.time()
    while time.time() - start < timeout:
        try:
            found = sb.execute_script("""
            (() => {
                const iframes = Array.from(document.querySelectorAll("iframe"));
                for (const f of iframes) {
                    const src = String(f.src || "");
                    if (src.includes("challenges.cloudflare.com")) return true;
                }
                return false;
            })();
            """)
            if found:
                print("✅ 检测到 Turnstile iframe")
                return True
        except Exception:
            pass

        time.sleep(1)

    print("⚠️ 未检测到 Turnstile iframe（可能是 shadow DOM 或动态加载）")
    return False


def get_turnstile_token(sb):
    """
    尽可能扫描所有 token 存放位置
    """
    try:
        token = sb.execute_script("""
        (() => {
            // 标准字段
            const standard =
                document.querySelector('input[name="cf-turnstile-response"]') ||
                document.querySelector('textarea[name="cf-turnstile-response"]');

            if (standard) {
                const v = (standard.value || "").trim();
                if (v.length > 20) return v;
            }

            // 动态 id: cf-chl-widget-xxxx_response
            const candidates = Array.from(document.querySelectorAll("input, textarea"))
                .filter(x => x.id && x.id.startsWith("cf-chl-widget-") && x.id.endsWith("_response"));

            for (const c of candidates) {
                const v = (c.value || "").trim();
                if (v.length > 20) return v;
            }

            // 有些站把 token 放在 data attribute
            const anyHidden = Array.from(document.querySelectorAll("input[type='hidden'], textarea"))
                .filter(x => (x.name || "").includes("turnstile") || (x.id || "").includes("turnstile"));

            for (const h of anyHidden) {
                const v = (h.value || "").trim();
                if (v.length > 20) return v;
            }

            // 极端情况：token 存 window 对象
            for (const k of Object.keys(window)) {
                try {
                    const v = window[k];
                    if (typeof v === "string" && v.length > 50 && v.includes(".")) {
                        // token 常有点号结构
                        if (v.length < 5000) return v;
                    }
                } catch(e) {}
            }

            return null;
        })();
        """)
        return token
    except Exception:
        return None


def wait_turnstile_token(sb, timeout=90):
    print("🧩 等待 Turnstile token ...")

    start = time.time()
    while time.time() - start < timeout:
        token = get_turnstile_token(sb)
        if token:
            print(f"✅ Turnstile token 已生成 (len={len(token)})")
            return token

        time.sleep(1)

    print("❌ 超时：未获取 Turnstile token")
    return None


def try_click_turnstile_many_times(sb, tries=3):
    """
    多次尝试点击 captcha，模拟真人反复点击/等待
    """
    for i in range(tries):
        print(f"☑️ 尝试通过 Turnstile (try {i+1}/{tries}) ...")

        try:
            sb.uc_gui_click_captcha()
            human_sleep(3, 6)
        except Exception as e:
            print(f"⚠️ uc_gui_click_captcha 异常: {e}")

        # 随机滚动一下，更像真人
        human_like_scroll(sb)

        # 每次点击后都看看 token 有没有出现
        token = get_turnstile_token(sb)
        if token:
            print("✅ 点击后 token 已出现")
            return token

    return None


def wait_next_button(sb, timeout=40):
    print("⏳ 等待 NEXT 按钮出现 ...")

    start = time.time()
    while time.time() - start < timeout:
        try:
            found = sb.execute_script("""
            (() => {
                const btns = Array.from(document.querySelectorAll("button"))
                    .filter(b => b.offsetParent !== null);

                for (const b of btns) {
                    const t = (b.innerText || "").trim().toLowerCase();
                    if (t.includes("next") || t.includes("다음")) return true;
                }
                return false;
            })();
            """)
            if found:
                print("✅ NEXT 按钮已出现")
                return True
        except Exception:
            pass

        time.sleep(1)

    print("❌ NEXT 按钮未出现")
    return False


def click_next_button(sb):
    print("🟢 尝试点击 NEXT ...")

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
            print("✅ NEXT 点击成功")
            return True
    except Exception as e:
        print("⚠️ NEXT click js failed:", e)

    print("❌ NEXT 点击失败")
    return False


def dump_turnstile_inputs(sb):
    """
    debug：打印页面里所有可能 token input
    """
    try:
        data = sb.execute_script("""
        (() => {
            const els = Array.from(document.querySelectorAll("input, textarea"))
                .filter(x =>
                    (x.name || "").includes("turnstile") ||
                    (x.id || "").includes("turnstile") ||
                    (x.name || "").includes("cf-turnstile") ||
                    (x.id || "").includes("cf-chl-widget")
                );

            return els.map(e => ({
                tag: e.tagName,
                id: e.id,
                name: e.name,
                value_len: (e.value || "").length
            }));
        })();
        """)
        print("🧾 页面 Turnstile 相关字段:", data)
    except Exception as e:
        print("⚠️ dump_turnstile_inputs failed:", e)


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

        # 关键：用 uc_open_with_reconnect 更像真人访问
        sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", reconnect_time=5.0)
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

        # ---------- 打开服务器页面 ----------
        print(f"🌐 打开服务器页面: {SERVER_URL}")
        sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=5.0)
        wait_react_loaded(sb)
        remove_ads(sb)

        human_like_scroll(sb)

        screenshot(sb, "01_server_page.png")

        # ---------- 点击续期 ----------
        if not click_renew_button(sb):
            screenshot(sb, "02_renew_not_found.png")
            raise Exception("❌ 未找到续期按钮")

        human_sleep(2, 4)
        screenshot(sb, "03_after_click_renew.png")

        # ---------- 等待 Turnstile iframe ----------
        wait_for_turnstile_iframe(sb, timeout=25)

        # ---------- 尝试 Turnstile ----------
        token = try_click_turnstile_many_times(sb, tries=4)
        screenshot(sb, "04_after_turnstile_click.png")

        # 如果多次点击后还没 token，再进入等待模式
        if not token:
            token = wait_turnstile_token(sb, timeout=90)

        if not token:
            dump_turnstile_inputs(sb)
            screenshot(sb, "05_no_turnstile_token.png")
            raise Exception("❌ 未获取 Turnstile token（可能被识别为自动化环境）")

        print("🎯 Turnstile token OK!")
        screenshot(sb, "06_turnstile_token_ready.png")

        # ---------- 等 NEXT ----------
        if not wait_next_button(sb, timeout=40):
            screenshot(sb, "07_no_next_button.png")
            raise Exception("❌ 未出现 NEXT（可能验证没真正通过）")

        screenshot(sb, "08_next_visible.png")

        # ---------- 点击 NEXT ----------
        if not click_next_button(sb):
            screenshot(sb, "09_next_click_failed.png")
            raise Exception("❌ NEXT 点击失败")

        print("⏳ 等待续期完成 ...")
        human_sleep(6, 10)

        screenshot(sb, "10_after_next.png")

        # ---------- 刷新确认 ----------
        print("🔄 刷新页面确认状态更新 ...")
        sb.refresh()
        wait_react_loaded(sb)
        remove_ads(sb)

        screenshot(sb, "11_after_refresh.png")

        print("=== 任务完成 ===")
        print("✅ 已执行 Turnstile + NEXT（请核对截图确认续期是否生效）")


if __name__ == "__main__":
    main()