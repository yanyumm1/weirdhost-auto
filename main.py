#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import random
import platform
import traceback
from pathlib import Path
from seleniumbase import SB
from typing import Optional, Dict, Any

# =================================================
# 配置
# =================================================
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")

TIMEOUT_WAIT_CF = 90        # Turnstile/CF 验证最长等待秒数
CLICK_RETRY_INTERVAL = 3    # 每次尝试点击间隔
MAX_CLICK_TRIES = 15        # 增加点击次数上限

TURNSTILE_IFRAME_SELECTOR = "iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], iframe[title*='widget']"
TURNSTILE_HIDDEN_SELECTOR = "input[name='cf-turnstile-response'], input[name='cf_captcha_kind']"

# 备用选择器
ALTERNATE_SELECTORS = [
    'iframe[title*="Cloudflare"]',
    'iframe[src*="cloudflare.com/cdn-cgi/challenge-platform"]',
    '.cf-turnstile',
    'div[data-sitekey]'
]

# =================================================
# 工具函数
# =================================================
def human_sleep(a=0.8, b=1.6):
    """更真实的随机延迟"""
    time.sleep(random.uniform(a, b))

def screenshot(sb, name: str):
    """保存截图并附加时间戳"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.png" if not name.endswith('.png') else name
    path = SCREENSHOT_DIR / filename
    try:
        sb.save_screenshot(str(path))
        print(f"📸 Screenshot saved: {path}")
        return True
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")
        return False

def _has_cf_clearance(sb: SB) -> bool:
    """检查是否已获得 cf_clearance cookie"""
    try:
        cookies = sb.get_cookies()
        for cookie in cookies:
            if cookie.get("name") == "cf_clearance":
                print(f"✅ cf_clearance found: {cookie['value'][:20]}...")
                return True
        return False
    except Exception:
        return False

def _get_turnstile_hidden_value(sb: SB) -> str:
    """获取隐藏的验证响应"""
    for selector in TURNSTILE_HIDDEN_SELECTOR.split(', '):
        try:
            elements = sb.find_elements(selector)
            for element in elements:
                val = sb.get_attribute(element, "value")
                if val and val.strip():
                    print(f"✅ Turnstile hidden value found (len={len(val)})")
                    return val.strip()
        except Exception:
            continue
    return ""

def _robust_click_with_retry(sb: SB, sel: str, tries: int = 3) -> bool:
    """更鲁棒的点击函数，带重试机制"""
    for attempt in range(1, tries + 1):
        try:
            # 先确保元素可见
            if not sb.is_element_visible(sel):
                sb.scroll_to(sel)
                time.sleep(0.5)
            
            # 尝试常规点击
            sb.click(sel)
            print(f"✅ Clicked {sel} (attempt {attempt}/{tries})")
            human_sleep(0.5, 1.0)
            return True
        except Exception as e:
            print(f"⚠️ Click attempt {attempt} failed for {sel}: {str(e)[:100]}")
            
            # 尝试 JavaScript 点击
            try:
                sb.execute_script("""
                    var element = document.querySelector(arguments[0]);
                    if (element) {
                        element.scrollIntoView({behavior: 'smooth', block: 'center'});
                        element.click();
                        return true;
                    }
                    return false;
                """, sel)
                print(f"✅ JavaScript click succeeded for {sel}")
                human_sleep(0.5, 1.0)
                return True
            except Exception as js_e:
                print(f"⚠️ JavaScript click failed: {str(js_e)[:100]}")
            
            if attempt < tries:
                human_sleep(0.5, 1.0)
    
    return False

def _find_turnstile_iframe(sb: SB) -> Optional[Dict[str, Any]]:
    """查找 Turnstile iframe，尝试多个选择器"""
    selectors = [TURNSTILE_IFRAME_SELECTOR] + ALTERNATE_SELECTORS
    
    for selector in selectors:
        try:
            if sb.is_element_visible(selector):
                iframe = sb.find_element(selector)
                loc = iframe.location_once_scrolled_into_view
                size = iframe.size
                
                return {
                    'element': iframe,
                    'x': loc.get('x', 0),
                    'y': loc.get('y', 0),
                    'width': size.get('width', 0),
                    'height': size.get('height', 0),
                    'selector': selector
                }
        except Exception:
            continue
    
    # 尝试通过属性查找
    try:
        iframes = sb.find_elements("iframe")
        for iframe in iframes:
            src = sb.get_attribute(iframe, "src") or ""
            title = sb.get_attribute(iframe, "title") or ""
            if "cloudflare" in src.lower() or "turnstile" in src.lower() or "widget" in title.lower():
                loc = iframe.location_once_scrolled_into_view
                size = iframe.size
                return {
                    'element': iframe,
                    'x': loc.get('x', 0),
                    'y': loc.get('y', 0),
                    'width': size.get('width', 0),
                    'height': size.get('height', 0),
                    'selector': 'by_attributes'
                }
    except Exception:
        pass
    
    return None

# =================================================
# Turnstile 处理函数
# =================================================
def try_click_turnstile(sb: SB) -> bool:
    """尝试点击 Turnstile 验证框，使用多种策略"""
    
    # 策略1：直接使用官方方法（如果可用）
    try:
        if hasattr(sb, 'uc_click_turnstile_iframe'):
            print("🔄 Using official uc_click_turnstile_iframe method")
            sb.uc_click_turnstile_iframe()
            human_sleep(1, 2)
            return True
    except Exception:
        pass
    
    # 策略2：查找并点击 iframe
    iframe_info = _find_turnstile_iframe(sb)
    if not iframe_info:
        print("⚠️ No Turnstile iframe found")
        return False
    
    print(f"🎯 Turnstile iframe found: x={iframe_info['x']}, y={iframe_info['y']}, "
          f"w={iframe_info['width']}, h={iframe_info['height']}")
    
    # 检查 iframe 尺寸
    if iframe_info['width'] < 50 or iframe_info['height'] < 50:
        print("⚠️ Iframe too small, may not be clickable")
        return False
    
    # 策略2a：点击 iframe 内部（尝试不同位置）
    click_positions = [
        (0.25, 0.5),  # 左侧中间
        (0.5, 0.5),   # 正中间
        (0.4, 0.6),   # 稍微偏右下
    ]
    
    for pos_idx, (x_ratio, y_ratio) in enumerate(click_positions):
        try:
            click_x = int(iframe_info['x'] + iframe_info['width'] * x_ratio)
            click_y = int(iframe_info['y'] + iframe_info['height'] * y_ratio)
            
            print(f"🖱️ Attempting click at position {pos_idx + 1}: ({click_x}, {click_y})")
            
            # 使用 UC 模式的 GUI 点击
            sb.uc_gui_click_x_y(click_x, click_y)
            print(f"✅ GUI click at position {pos_idx + 1} executed")
            
            # 检查是否成功
            human_sleep(1, 1.5)
            
            # 快速检查响应
            if _get_turnstile_hidden_value(sb):
                print("✅ Turnstile responded immediately")
                return True
                
        except Exception as e:
            print(f"⚠️ Click at position {pos_idx + 1} failed: {e}")
            human_sleep(0.5, 1)
    
    # 策略3：尝试直接执行验证脚本
    try:
        print("🔄 Trying JavaScript challenge solver")
        sb.execute_script("""
            // 尝试触发验证
            var iframes = document.querySelectorAll('iframe');
            iframes.forEach(iframe => {
                try {
                    if (iframe.contentWindow && iframe.contentWindow.document) {
                        var checkboxes = iframe.contentWindow.document.querySelectorAll('input[type="checkbox"]');
                        checkboxes.forEach(cb => {
                            cb.click();
                            cb.checked = true;
                        });
                    }
                } catch(e) {}
            });
        """)
        human_sleep(1, 2)
        return True
    except Exception as e:
        print(f"⚠️ JavaScript solver failed: {e}")
    
    return False

def wait_turnstile_pass(sb: SB, timeout: int = TIMEOUT_WAIT_CF) -> bool:
    """等待 Turnstile 验证通过"""
    start_time = time.time()
    click_count = 0
    last_status_time = start_time
    
    print(f"⏳ Waiting for Turnstile verification (timeout: {timeout}s)")
    
    while time.time() - start_time < timeout:
        elapsed = int(time.time() - start_time)
        
        # 每15秒打印一次状态
        if time.time() - last_status_time >= 15:
            print(f"⏰ Still waiting... ({elapsed}/{timeout}s elapsed)")
            screenshot(sb, f"status_elapsed_{elapsed}s.png")
            last_status_time = time.time()
        
        # 检查成功条件
        if _get_turnstile_hidden_value(sb):
            print(f"✅ Turnstile response received after {elapsed}s")
            return True
            
        if _has_cf_clearance(sb):
            print(f"✅ cf_clearance cookie found after {elapsed}s")
            return True
        
        # 检查 iframe 是否消失
        iframe_visible = False
        for selector in [TURNSTILE_IFRAME_SELECTOR] + ALTERNATE_SELECTORS:
            if sb.is_element_visible(selector):
                iframe_visible = True
                break
        
        if not iframe_visible:
            print(f"✅ Turnstile iframe disappeared after {elapsed}s")
            # 再次确认有验证响应
            human_sleep(1, 2)
            if _get_turnstile_hidden_value(sb) or _has_cf_clearance(sb):
                return True
        
        # 尝试点击（如果还有次数）
        if click_count < MAX_CLICK_TRIES and elapsed < timeout * 0.8:
            click_count += 1
            print(f"🔁 Attempt {click_count}/{MAX_CLICK_TRIES} to solve Turnstile...")
            
            if try_click_turnstile(sb):
                print(f"✅ Turnstile interaction successful (attempt {click_count})")
                # 给验证一些时间处理
                human_sleep(2, 3)
            else:
                print(f"⚠️ Turnstile interaction failed (attempt {click_count})")
            
            screenshot(sb, f"turnstile_attempt_{click_count:02d}.png")
        else:
            # 等待期，减少频繁检查
            wait_time = random.uniform(2, 4)
            print(f"⏳ Waiting {wait_time:.1f}s before next check...")
            time.sleep(wait_time)
    
    print(f"❌ Turnstile verification timeout after {elapsed}s")
    screenshot(sb, "turnstile_timeout.png")
    return False

# =================================================
# 主流程优化
# =================================================
def main():
    """主执行函数"""
    if not SERVER_URL:
        raise ValueError("❌ WEIRDHOST_SERVER_URL environment variable is required")
    
    print(f"🚀 Starting Weirdhost auto-renewal for: {SERVER_URL}")
    
    # 设置虚拟显示（仅Linux）
    display = None
    if platform.system().lower() == "linux" and not os.environ.get("DISPLAY"):
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=False, size=(1920, 1080))
            display.start()
            os.environ["DISPLAY"] = display.new_display_var
            print("🖥️ Xvfb started")
        except ImportError:
            print("⚠️ Install pyvirtualdisplay for headless operation on Linux")
    
    try:
        # 浏览器配置
        chrome_args = [
            '--no-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--window-size=1920,1080',
            '--disable-dev-shm-usage',
            '--disable-gpu',  # 仅headless时需要
            '--disable-software-rasterizer',
            '--disable-extensions',
            '--disable-background-networking',
            '--disable-sync',
            '--disable-default-apps',
            '--disable-translate',
            '--disable-features=site-per-process',
            '--disable-web-security',
            '--allow-running-insecure-content',
            '--disable-notifications',
            '--disable-popup-blocking',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-background-timer-throttling',
            '--disable-client-side-phishing-detection',
            '--disable-component-update',
            '--disable-domain-reliability',
            '--disable-features=AudioServiceOutOfProcess',
            '--disable-hang-monitor',
            '--disable-ipc-flooding-protection',
            '--disable-breakpad',
            '--disable-crash-reporter',
            '--metrics-recording-only',
            '--no-first-run',
            '--safebrowsing-disable-auto-update',
            '--password-store=basic',
            '--use-mock-keychain',
        ]
        
        with SB(
            uc=True,
            headless2=True,  # 使用headless2模式（更好的兼容性）
            locale_code="en-US",
            agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            protocol="http",
            wire=True,
            chromium_arg=' '.join(chrome_args),
            disable_csp=True,
            do_not_track=True,
            skip_js_waits=False,  # 改为False，确保页面加载完成
            undetectable=True,    # 添加反检测
            page_load_strategy="normal",  # 页面加载策略
        ) as sb:
            
            # 设置超时（通过SeleniumBase方法）
            sb.set_page_load_timeout(60)
            sb.set_script_timeout(60)
            
            # 1. 访问首页建立会话
            print("🌐 Visiting hub.weirdhost.xyz to establish session...")
            sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", reconnect_time=5)
            human_sleep(2, 3)
            screenshot(sb, "00_homepage.png")
            
            # 2. 注入Cookie登录
            if REMEMBER_WEB_COOKIE:
                print("🍪 Injecting remember_web cookie...")
                # 确保在正确的域
                if "weirdhost" in sb.get_current_url():
                    sb.add_cookie({
                        "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                        "value": REMEMBER_WEB_COOKIE,
                        "domain": ".weirdhost.xyz",
                        "path": "/",
                        "secure": True,
                        "httpOnly": True,
                        "sameSite": "Lax"
                    })
                    print("✅ Cookie injected, refreshing...")
                    sb.refresh()
                    human_sleep(3, 4)
                    screenshot(sb, "01_logged_in.png")
                else:
                    print("⚠️ Not on weirdhost domain, skipping cookie injection")
            
            # 3. 访问服务器页面
            print(f"🔗 Navigating to server page: {SERVER_URL}")
            sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=10)
            human_sleep(3, 5)
            screenshot(sb, "02_server_page.png")
            
            # 4. 点击续期按钮
            print("🔍 Looking for renewal button...")
            renewal_selectors = [
                '//button[.//span[contains(text(), "시간 추가")]]',
                '//button[contains(text(), "시간 추가")]',
                '//button[contains(text(), "Renew")]',
                '//button[contains(@class, "renew")]',
                '//button[contains(@id, "renew")]',
                '//a[contains(text(), "시간 추가")]',
                '//a[contains(text(), "Renew")]',
            ]
            
            button_found = False
            for selector in renewal_selectors:
                try:
                    if sb.is_element_visible(selector, timeout=10):
                        print(f"✅ Found renewal button with selector: {selector}")
                        sb.highlight(selector, loops=2)
                        human_sleep(1, 2)
                        
                        if _robust_click_with_retry(sb, selector, tries=3):
                            button_found = True
                            print("✅ Successfully clicked renewal button")
                            screenshot(sb, "03_after_renew_click.png")
                            break
                except Exception as e:
                    print(f"⚠️ Selector {selector} failed: {e}")
                    continue
            
            if not button_found:
                # 最后尝试：查找所有按钮并点击可能的续期按钮
                try:
                    buttons = sb.find_elements("button")
                    for i, button in enumerate(buttons):
                        text = sb.get_text(button)
                        if text and ("시간" in text or "Renew" in text or "추가" in text):
                            print(f"🗳️ Found possible button text: {text}")
                            sb.click(button)
                            button_found = True
                            break
                except Exception:
                    pass
            
            if not button_found:
                screenshot(sb, "renew_button_not_found.png")
                raise RuntimeError("❌ Could not find or click renewal button")
            
            # 5. 等待验证通过
            print("🛡️ Waiting for Cloudflare Turnstile verification...")
            
            # 先给一点时间让验证框加载
            human_sleep(2, 3)
            screenshot(sb, "04_before_turnstile.png")
            
            # 等待验证通过
            success = wait_turnstile_pass(sb, timeout=TIMEOUT_WAIT_CF)
            
            if success:
                print("✅ Turnstile verification passed!")
                screenshot(sb, "05_verification_passed.png")
                
                # 验证成功，等待页面加载完成
                human_sleep(3, 5)
                
                # 检查是否有成功消息
                try:
                    success_selectors = [
                        '//*[contains(text(), "success") or contains(text(), "성공")]',
                        '//*[contains(text(), "extended") or contains(text(), "연장")]',
                        '.alert-success',
                        '.success-message',
                    ]
                    
                    for selector in success_selectors:
                        if sb.is_element_visible(selector, timeout=10):
                            success_msg = sb.get_text(selector)
                            print(f"🎉 Success message found: {success_msg[:100]}...")
                            break
                except Exception:
                    pass
                
                print("✅ Auto-renewal process completed successfully!")
                return True
            else:
                print("❌ Turnstile verification failed or timed out")
                screenshot(sb, "06_verification_failed.png")
                raise RuntimeError("Cloudflare Turnstile verification failed")
    
    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        print(f"🔍 Traceback: {traceback.format_exc()}")
        raise
    
    finally:
        if display:
            display.stop()
            print("🖥️ Xvfb stopped")

if __name__ == "__main__":
    try:
        main()
        print("✨ Script finished successfully!")
    except Exception as e:
        print(f"💥 Script failed with error: {e}")
        exit(1)