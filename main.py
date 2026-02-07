import os
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def wait_for_turnstile(page, timeout=60000):
    """
    等待 Cloudflare Turnstile 验证完成
    """
    print("检测是否出现 Cloudflare Turnstile 验证...")

    try:
        # 等待 Turnstile iframe 出现（如果存在）
        page.wait_for_selector('iframe[src*="turnstile"]', timeout=10000)
        print("检测到 Turnstile 小组件，等待验证通过...")

    except PlaywrightTimeoutError:
        print("未检测到 Turnstile，可能无需验证。")
        return True

    try:
        # 等待 token 生成
        page.wait_for_function("""
            () => {
                const input = document.querySelector('input[name="cf-turnstile-response"]');
                return input && input.value && input.value.length > 0;
            }
        """, timeout=timeout)

        print("✅ Turnstile 验证已通过")
        return True

    except PlaywrightTimeoutError:
        print("❌ Turnstile 验证超时")
        page.screenshot(path="turnstile_timeout.png")
        return False


def add_server_time(server_url="https://hub.weirdhost.xyz/server/a79a2b26"):

    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')
    pterodactyl_email = os.environ.get('PTERODACTYL_EMAIL')
    pterodactyl_password = os.environ.get('PTERODACTYL_PASSWORD')

    if not (remember_web_cookie or (pterodactyl_email and pterodactyl_password)):
        print("错误: 缺少登录凭据")
        return False

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(90000)

        try:

            # ===== Cookie 登录 =====
            if remember_web_cookie:
                print("尝试 Cookie 登录")

                session_cookie = {
                    'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                    'value': remember_web_cookie,
                    'domain': 'hub.weirdhost.xyz',
                    'path': '/',
                    'httpOnly': True,
                    'secure': True,
                    'sameSite': 'Lax'
                }

                page.context.add_cookies([session_cookie])
                page.goto(server_url, wait_until="domcontentloaded")

                if "login" in page.url:
                    print("Cookie 失效")
                    page.context.clear_cookies()
                    remember_web_cookie = None
                else:
                    print("Cookie 登录成功")

            # ===== 账号密码登录 =====
            if not remember_web_cookie:

                login_url = "https://hub.weirdhost.xyz/auth/login"
                page.goto(login_url)

                page.fill('input[name="username"]', pterodactyl_email)
                page.fill('input[name="password"]', pterodactyl_password)

                with page.expect_navigation():
                    page.click('button[type="submit"]')

                if "login" in page.url:
                    print("登录失败")
                    return False

            # ===== 进入服务器页面 =====
            if page.url != server_url:
                page.goto(server_url)

            # ===== 点击 시간 추가 =====
            print("查找 '시간 추가' 按钮")

            add_button = page.locator('button:has-text("시간 추가")')
            add_button.wait_for(state='visible')
            add_button.click()

            print("已点击时间追加按钮")

            # ===== 等待 Turnstile =====
            if not wait_for_turnstile(page):
                return False

            # 等服务器处理
            time.sleep(5)

            print("🎉 时间追加流程完成")
            browser.close()
            return True

        except Exception as e:
            print(f"未知错误: {e}")
            page.screenshot(path="general_error.png")
            browser.close()
            return False


if __name__ == "__main__":
    print("开始执行添加服务器时间任务...")
    success = add_server_time()

    if success:
        exit(0)
    else:
        exit(1)