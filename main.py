import os
import time
import random
from seleniumbase import SB

REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")
SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")

os.makedirs("screenshots", exist_ok=True)

def screenshot(sb, name):
    sb.save_screenshot(f"screenshots/{name}")
    print(f"📸 Screenshot saved: screenshots/{name}")

def sleep(a=1.5, b=3.0):
    time.sleep(random.uniform(a, b))

def wait_loaded(sb):
    sb.wait_for_ready_state_complete(timeout=30)
    sleep(2, 3)

# ⭐ 真正滚动 Weirdhost 内容区
def scroll_real_container(sb):
    sb.execute_script("""
    (() => {
        const candidates = [
            document.querySelector("main"),
            document.querySelector('[role="main"]'),
            document.querySelector(".content"),
            document.querySelector("#root")
        ].filter(Boolean);

        for (const el of candidates) {
            el.scrollTo(0, el.scrollHeight);
        }
    })();
    """)
    sleep(2, 3)

def click_renew(sb):
    print("🕒 查找 Renew / 시간 추가（真实容器）")

    for _ in range(3):
        scroll_real_container(sb)

        clicked = sb.execute_script("""
        (() => {
            const keys = ["renew", "시간", "추가", "extend"];
            const els = [...document.querySelectorAll("button, [role='button'], a")];

            for (const el of els) {
                const t = (el.innerText || "").toLowerCase();
                if (keys.some(k => t.includes(k))) {
                    el.scrollIntoView({block: "center"});
                    el.click();
                    return true;
                }
            }
            return false;
        })();
        """)

        if clicked:
            print("✅ Renew 点击成功")
            return True

        sleep(1.5, 2.5)

    return False

def wait_next(sb, timeout=60):
    print("⏳ 等待 NEXT / 다음")
    start = time.time()

    while time.time() - start < timeout:
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
            return True
        time.sleep(1)

    return False

def click_next(sb):
    return sb.execute_script("""
    (() => {
        for (const el of document.querySelectorAll("button, [role='button']")) {
            const t = (el.innerText || "").toLowerCase();
            if (el.offsetParent && (t.includes("next") || t.includes("다음"))) {
                el.scrollIntoView({block:"center"});
                el.click();
                return true;
            }
        }
        return false;
    })();
    """)

def main():
    print("🚀 Weirdhost 自动续期（最终稳定版）")

    with SB(
        uc=True,
        headless=False,
        locale="en",
        chromium_arg="--start-maximized --window-size=1920,1080"
    ) as sb:

        sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", 5)
        wait_loaded(sb)

        if REMEMBER_WEB_COOKIE:
            sb.add_cookie({
                "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                "value": REMEMBER_WEB_COOKIE,
                "domain": "hub.weirdhost.xyz",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            })
            sb.refresh()
            wait_loaded(sb)

        sb.uc_open_with_reconnect(SERVER_URL, 5)
        wait_loaded(sb)

        screenshot(sb, "01_server_page.png")

        if not click_renew(sb):
            screenshot(sb, "renew_not_visible.png")
            raise Exception("❌ Renew / 时间追加 未出现（未滚到）")

        screenshot(sb, "02_after_renew.png")

        print("🛡️ 等待 Turnstile")
        sleep(15, 20)

        try:
            sb.uc_gui_click_captcha()
        except Exception:
            pass

        sleep(10, 15)

        if not wait_next(sb):
            screenshot(sb, "no_next.png")
            raise Exception("❌ NEXT 未出现")

        click_next(sb)
        sleep(6, 10)

        screenshot(sb, "done.png")
        print("🎉 Weirdhost 续期完成")

if __name__ == "__main__":
    main()