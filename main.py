import os
import time
import random
from seleniumbase import SB

# =========================
# 环境变量配置（保留你的写法）
# =========================
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

# =========================
# SOCKS5 代理（你提供的）
# =========================
SOCKS5_PROXY = "socks5://9afd1229:51e7ce204913@121.163.216.45:25525"

# =========================
# 截图目录
# =========================
os.makedirs("screenshots", exist_ok=True)


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


def human_scroll(sb):
    try:
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.25)")
        human_sleep()
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.55)")
        human_sleep()
        sb.execute_script("window.scrollTo(0, 0)")
        human_sleep()
    except Exception:
        pass


def click_renew_button(sb):
    print("🕒 查找 Renew/시간 추가 按钮 ...")

    selectors = [
        'button[color="primary"]',
        'button:contains("시간 추가")',
        'button:contains("Renew")',
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

    # JS fallback
    try:
        clicked = sb.execute_script("""
        (() => {
            const btns = Array.from(document.querySelectorAll("button"));
            const keys = ["renew", "시간", "추가", "extend", "add"];
            for (const b of btns) {
                const t = (b.innerText || "").trim().toLowerCase();
                if (!t) continue;
                for (const k of keys) {
                    if (t.includes(k)) {
                        b.scrollIntoView({block:"center"});
                        b.click();
                        return true;
                    }
                }
            }
            return false;
        })();
        """)
        if clicked:
            print("✅ JS fallback 点击成功（文本匹配按钮）")
            return True
    except Exception:
        pass

    return False


def wait_next_button(sb, timeout=45):
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
        chromium_arg=f"--window-size=1920,1080 --proxy-server={SOCKS5_PROXY}"
    ) as sb:

        print("🚀 浏览器启动 (UC Mode + SOCKS5 Proxy)")

        # 先打开 hub
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
        human_scroll(sb)

        screenshot(sb, "01_server_page.png")

        # ---------- 点击续期 ----------
        if not click_renew_button(sb):
            print("❌ 未找到 Renew 按钮")
            screenshot(sb, "02_renew_not_found.png")
            return

        human_sleep(2, 4)
        screenshot(sb, "03_after_click_renew.png")

        # ---------- Turnstile ----------
        print("☑️ 尝试通过 Cloudflare Turnstile ...")

        try:
            sb.uc_gui_click_captcha()
            print("✅ 已执行 uc_gui_click_captcha()")
        except Exception as e:
            print(f"⚠️ 未检测到验证码或点击失败: {e}")

        human_sleep(4, 6)
        screenshot(sb, "04_after_turnstile_click.png")

        # ---------- 等 NEXT ----------
        if not wait_next_button(sb, timeout=60):
            screenshot(sb, "05_no_next_button.png")
            raise Exception("❌ 未出现 NEXT（说明 Turnstile 仍未通过）")

        screenshot(sb, "06_next_visible.png")

        # ---------- 点击 NEXT ----------
        if not click_next_button(sb):
            screenshot(sb, "07_next_click_failed.png")
            raise Exception("❌ NEXT 点击失败")

        human_sleep(5, 8)
        screenshot(sb, "08_after_next.png")

        # ---------- 刷新确认 ----------
        print("🔄 刷新页面确认续期状态 ...")
        sb.refresh()
        wait_react_loaded(sb)

        remove_ads(sb)
        screenshot(sb, "09_after_refresh.png")

        print("=== 任务完成 ===")
        print("✅ 已执行: Renew -> Turnstile -> NEXT -> Refresh")


if __name__ == "__main__":
    main()