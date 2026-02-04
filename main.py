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
    """
    React/Vue 页面常见：readyState 完成后还会异步渲染。
    """
    sb.wait_for_ready_state_complete(timeout=timeout)
    sb.sleep(2)


def remove_ads(sb):
    """
    Weirdhost 页面有 iframe 广告可能挡住按钮
    """
    try:
        sb.execute_script("""
        document.querySelectorAll("iframe").forEach(f=>f.remove());
        """)
    except Exception:
        pass


def get_cookie_value(sb, cookie_name):
    try:
        cookies = sb.get_cookies()
        for c in cookies:
            if c.get("name") == cookie_name:
                return c.get("value")
    except Exception:
        return None
    return None


def wait_for_cf_clearance(sb, timeout=25):
    """
    Cloudflare 放行后会出现 cf_clearance
    """
    print("🧩 等待 Cloudflare cf_clearance ...")

    start = time.time()
    while time.time() - start < timeout:
        cf_clearance = get_cookie_value(sb, "cf_clearance")
        if cf_clearance:
            print("✅ 已获取 cf_clearance")
            return cf_clearance
        sb.sleep(1)

    print("❌ 超时：未获取 cf_clearance")
    return None


def try_click_turnstile(sb):
    """
    尝试点击 Cloudflare Turnstile。
    SeleniumBase 的 uc_gui_click_captcha() 很好用，但不一定每次都能点到。
    """
    print("☑️ 尝试通过 Cloudflare Turnstile ...")

    try:
        sb.uc_gui_click_captcha()
        sb.sleep(4)
        print("✅ 已执行 uc_gui_click_captcha()")
        return True
    except Exception as e:
        print(f"⚠️ 未检测到验证码或点击失败: {e}")
        return False


def find_and_click_renew_button(sb):
    """
    Renew/시간 추가 按钮点击逻辑（多 selector + 文本匹配）
    """
    print("🕒 查找 Renew/시간 추가 按钮 ...")

    selectors = [
        'button[color="primary"]',
        'button.MuiButton-containedPrimary',
        'div[class*="RenewBox"] button',
        'button:contains("Renew")',
        'button:contains("Extend")',
        'button:contains("Add Time")',
        'button:contains("시간")',
        'button:contains("추가")',
    ]

    # 先尝试 SeleniumBase 内置 contains 语法（它支持）
    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=6)
            sb.scroll_to(sel)
            sb.click(sel)
            print(f"✅ 点击成功: {sel}")
            return True
        except Exception:
            pass

    # JS fallback：扫描所有 button，看文本是否包含 renew/시간
    try:
        clicked = sb.execute_script("""
        const btns = Array.from(document.querySelectorAll("button"));
        const keywords = ["renew", "extend", "add time", "시간", "추가"];

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
            print("✅ JS fallback 点击成功（通过 innerText 匹配）")
            return True
    except Exception:
        pass

    print("❌ 未找到续期按钮")
    return False


def wait_modal_open(sb, timeout=10):
    """
    等待续期弹窗出现。
    """
    print("🪟 等待续期弹窗出现 ...")

    modal_selectors = [
        "#renew-modal",
        '[id*="renew"]',
        'div[role="dialog"]',
        ".MuiDialog-root",
        ".modal",
    ]

    for sel in modal_selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=timeout)
            print(f"✅ 检测到弹窗: {sel}")
            return sel
        except Exception:
            pass

    print("⚠️ 未检测到明显弹窗（可能直接触发续期流程）")
    return None


def wait_modal_close(sb, timeout=20):
    """
    很多站点续期成功后 modal 会自动关闭。
    """
    print("⏳ 等待弹窗关闭（如果存在）...")

    start = time.time()
    while time.time() - start < timeout:
        # 常见 modal selector
        exists = sb.execute_script("""
        return !!(
            document.querySelector("#renew-modal") ||
            document.querySelector(".MuiDialog-root") ||
            document.querySelector('div[role="dialog"]')
        );
        """)
        if not exists:
            print("✅ 弹窗已关闭")
            return True

        sb.sleep(1)

    print("⚠️ 弹窗未关闭（可能站点不会自动关闭）")
    return False


def wait_possible_success_toast(sb, timeout=15):
    """
    等待页面出现 success toast（很多站点会弹一个 toast）
    """
    print("🔎 等待成功提示（toast/alert）...")

    keywords = ["success", "renewed", "completed", "done", "성공", "완료"]

    start = time.time()
    while time.time() - start < timeout:
        found = sb.execute_script("""
        const keywords = arguments[0];
        const els = Array.from(document.querySelectorAll("div,span,p"));
        for (const el of els) {
            const txt = (el.innerText || "").trim().toLowerCase();
            if (!txt) continue;
            for (const k of keywords) {
                if (txt.includes(k)) {
                    return txt;
                }
            }
        }
        return null;
        """, keywords)

        if found:
            print(f"✅ 检测到疑似成功提示: {found[:120]}")
            return True

        sb.sleep(1)

    print("⚠️ 未检测到 success toast（不代表失败）")
    return False


def force_refresh_and_check(sb):
    """
    刷新页面让状态更新（React 经常不会自动刷新）
    """
    print("🔄 刷新页面确认续期状态 ...")
    sb.refresh()
    wait_react_loaded(sb)
    remove_ads(sb)


def main():
    print("=== Weirdhost 自动续期启动 ===")

    if not SERVER_URL:
        raise Exception("❌ 环境变量 WEIRDHOST_SERVER_URL 未设置！")

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

        # ---------- 打开服务器页面 ----------
        print(f"🌐 打开服务器页面: {SERVER_URL}")
        sb.open(SERVER_URL)
        wait_react_loaded(sb)
        remove_ads(sb)

        screenshot(sb, "01_server_page.png")

        # ---------- 点击续期 ----------
        if not find_and_click_renew_button(sb):
            screenshot(sb, "02_renew_not_found.png")
            raise Exception("❌ 未找到 Renew/时间追加 按钮")

        sb.sleep(2)
        modal_sel = wait_modal_open(sb, timeout=8)

        screenshot(sb, "03_after_click_renew.png")

        # ---------- Cloudflare ----------
        try_click_turnstile(sb)
        screenshot(sb, "04_after_turnstile_click.png")

        # 等待 cf_clearance
        cf_clearance = wait_for_cf_clearance(sb, timeout=30)
        if not cf_clearance:
            screenshot(sb, "05_no_cf_clearance.png")
            raise Exception("❌ Cloudflare 未放行（无 cf_clearance）")

        # ---------- 等待页面自动续期 ----------
        # 人工续期流程里：打勾后不需要 submit
        # 所以这里就是等待请求完成 + UI变化
        print("⏳ 等待续期动作自动完成 ...")

        wait_possible_success_toast(sb, timeout=10)

        # 等待弹窗关闭（如果会自动关闭）
        wait_modal_close(sb, timeout=15)

        sb.sleep(2)
        screenshot(sb, "06_after_wait.png")

        # ---------- 强制刷新确认 ----------
        force_refresh_and_check(sb)
        screenshot(sb, "07_after_refresh.png")

        print("✅ 脚本执行结束：已完成续期流程（建议人工核对截图）")
        print("=== 任务完成 ===")


if __name__ == "__main__":
    main()