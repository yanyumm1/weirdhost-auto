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
    sb.save_screenshot(f"screenshots/{name}")
    print(f"📸 Screenshot saved: screenshots/{name}")

def sleep(a=2, b=4):
    time.sleep(random.uniform(a, b))

def wait_loaded(sb):
    sb.wait_for_ready_state_complete(timeout=30)
    sleep(2, 3)

def scroll_container(sb):
    """滚动页面底部，适应 Weirdhost 内部容器"""
    sb.execute_script("""
    (() => {
        const els = [
            document.querySelector("main"),
            document.querySelector('[role="main"]'),
            document.querySelector(".content"),
            document.querySelector("#root")
        ].filter(Boolean);

        els.forEach(el => el.scrollTo(0, el.scrollHeight));
    })();
    """)
    sleep(2, 3)

# =========================
# Cloudflare 判断
# =========================
def cf_cookie_present(sb):
    try:
        return any(
            c["name"] in ("cf_clearance", "__cf_bm")
            for c in sb.get_cookies()
        )
    except Exception:
        return False

def wait_cf_pass(sb, timeout=120):
    print("🛡️ 等待 Cloudflare Turnstile 放行")
    start = time.time()
    while time.time() - start < timeout:
        if cf_cookie_present(sb):
            print("✅ CF Cookie 已生成")
            return True

        iframe_done = sb.execute_script("""
        (() => {
            const f = [...document.querySelectorAll("iframe")]
              .filter(i => (i.src || "").includes("challenges.cloudflare.com"));
            if (f.length === 0) return false;
            return f.some(i => i.style.display === "none");
        })();
        """)
        if iframe_done:
            print("✅ CF iframe 已释放")
            return True

        time.sleep(1)

    print("❌ CF 超时")
    return False

# =========================
# Renew / 시간 추가 按钮
# =========================
def trigger_renew_click(sb):
    """尝试点击 Renew / 시간 추가，第一次触发 CF，第二次完成续期"""
    print("🖱️ 尝试点击 시간 추가")
    scroll_container(sb)
    sleep(1.5, 2.5)
    try:
        sb.execute_script("""
        (() => {
            const keys = ["시간", "추가", "renew", "extend"];
            for (const el of document.querySelectorAll("button, [role='button'], div")) {
                const t = (el.innerText || "").toLowerCase();
                if (keys.some(k => t.includes(k)) && el.offsetParent) {
                    el.scrollIntoView({block:"center"});
                    el.click();
                    return true;
                }
            }
            return false;
        })();
        """)
        print("🟡 已尝试点击 시간 추가")
    except Exception as e:
        print("⚠️ 点击失败:", e)

# =========================
# NEXT / 다음
# =========================
def wait_next(sb, timeout=60):
    print("⏳ 等待 NEXT / 다음 按钮")
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
            print("✅ NEXT 出现")
            return True
        time.sleep(1)
    return False

def click_next(sb):
    clicked = sb.execute_script("""
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
    if clicked:
        print("✅ NEXT 点击成功")
    return clicked

# =========================
# 主流程
# =========================
def main():
    print("🚀 Weirdhost 自动续期（两步点击 + CF 顺序版）")

    if not SERVER_URL:
        raise Exception("❌ WEIRDHOST_SERVER_URL 未设置")

    with SB(
        uc=True,
        headless=False,
        locale="en",
        chromium_arg="--start-maximized --window-size=1920,1080"
    ) as sb:

        # 打开 Weirdhost 主站
        sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", 5)
        wait_loaded(sb)

        # Cookie 登录
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
            wait_loaded(sb)

        # 打开服务器页面
        sb.uc_open_with_reconnect(SERVER_URL, 5)
        wait_loaded(sb)
        screenshot(sb, "01_server_page.png")

        # ⭐ 第一次点击：触发 CF
        trigger_renew_click(sb)
        sleep(2, 4)

        # 尝试点一次 CF 勾选
        try:
            sb.uc_gui_click_captcha()
        except Exception:
            pass

        # 等 CF 放行
        if not wait_cf_pass(sb):
            screenshot(sb, "cf_failed.png")
            raise Exception("❌ Cloudflare 未通过")

        screenshot(sb, "02_cf_passed.png")

        # ⭐ 第二次点击：真正续期
        trigger_renew_click(sb)
        sleep(2, 4)
        screenshot(sb, "03_after_renew.png")

        # 等 NEXT
        if not wait_next(sb):
            screenshot(sb, "no_next.png")
            raise Exception("❌ NEXT 未出现")

        click_next(sb)
        sleep(6, 10)
        screenshot(sb, "04_done.png")

        print("🎉 Weirdhost 自动续期完成")

if __name__ == "__main__":
    main()