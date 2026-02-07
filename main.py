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
MAX_CLICK_TRIES = 15        # Turnstile 最大尝试次数

TURNSTILE_IFRAME_SELECTOR = "iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], iframe[title*='widget']"
TURNSTILE_HIDDEN_SELECTOR = "input[name='cf-turnstile-response'], input[name='cf_captcha_kind']"
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
    time.sleep(random.uniform(a, b))

def screenshot(sb, name: str):
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
    try:
        for c in sb.get_cookies():
            if c.get("name") == "cf_clearance":
                print(f"✅ cf_clearance found: {c['value'][:20]}...")
                return True
        return False
    except Exception:
        return False

def _get_turnstile_hidden_value(sb: SB) -> str:
    for sel in TURNSTILE_HIDDEN_SELECTOR.split(", "):
        try:
            elements = sb.find_elements(sel)
            for el in elements:
                val = sb.get_attribute(el, "value")
                if val and val.strip():
                    print(f"✅ Turnstile hidden value found (len={len(val)})")
                    return val.strip()
        except Exception:
            continue
    return ""

def _robust_click_with_retry(sb: SB, sel: str, tries: int = 3) -> bool:
    for attempt in range(1, tries + 1):
        try:
            if not sb.is_element_visible(sel):
                sb.scroll_to(sel)
                time.sleep(0.5)
            sb.click(sel)
            print(f"✅ Clicked {sel} (attempt {attempt}/{tries})")
            human_sleep(0.5, 1.0)
            return True
        except Exception as e:
            print(f"⚠️ Click attempt {attempt} failed for {sel}: {str(e)[:100]}")
            try:
                sb.execute_script("""
                    var element = document.querySelector(arguments[0]);
                    if (element) { element.scrollIntoView({behavior:'smooth',block:'center'}); element.click(); return true;}
                    return false;
                """, sel)
                print(f"✅ JavaScript click succeeded for {sel}")
                human_sleep(0.5, 1.0)
                return True
            except Exception as js_e:
                print(f"⚠️ JavaScript click failed: {str(js_e)[:100]}")
        human_sleep(0.5, 1.0)
    return False

def _find_turnstile_iframe(sb: SB) -> Optional[Dict[str, Any]]:
    selectors = [TURNSTILE_IFRAME_SELECTOR] + ALTERNATE_SELECTORS
    for sel in selectors:
        try:
            if sb.is_element_visible(sel):
                iframe = sb.find_element(sel)
                loc = iframe.location_once_scrolled_into_view
                size = iframe.size
                return {'element': iframe, 'x': loc.get('x',0), 'y': loc.get('y',0), 
                        'width': size.get('width',0), 'height': size.get('height',0), 'selector': sel}
        except Exception:
            continue
    try:
        iframes = sb.find_elements("iframe")
        for iframe in iframes:
            src = sb.get_attribute(iframe, "src") or ""
            title = sb.get_attribute(iframe, "title") or ""
            if "cloudflare" in src.lower() or "turnstile" in src.lower() or "widget" in title.lower():
                loc = iframe.location_once_scrolled_into_view
                size = iframe.size
                return {'element': iframe, 'x': loc.get('x',0), 'y': loc.get('y',0),
                        'width': size.get('width',0), 'height': size.get('height',0), 'selector':'by_attributes'}
    except Exception:
        pass
    return None

def try_click_turnstile(sb: SB) -> bool:
    try:
        if hasattr(sb, 'uc_click_turnstile_iframe'):
            sb.uc_click_turnstile_iframe()
            human_sleep(1,2)
            return True
    except Exception:
        pass
    iframe_info = _find_turnstile_iframe(sb)
    if not iframe_info:
        print("⚠️ No Turnstile iframe found")
        return False
    print(f"🎯 Turnstile iframe at x={iframe_info['x']}, y={iframe_info['y']}, w={iframe_info['width']}, h={iframe_info['height']}")
    if iframe_info['width']<50 or iframe_info['height']<50:
        print("⚠️ Iframe too small to click")
        return False
    positions = [(0.25,0.5),(0.5,0.5),(0.4,0.6)]
    for idx,(xr,yr) in enumerate(positions):
        try:
            x = int(iframe_info['x']+iframe_info['width']*xr)
            y = int(iframe_info['y']+iframe_info['height']*yr)
            sb.uc_gui_click_x_y(x,y)
            print(f"✅ GUI click at position {idx+1}")
            human_sleep(1,1.5)
            if _get_turnstile_hidden_value(sb):
                return True
        except Exception as e:
            print(f"⚠️ Click attempt {idx+1} failed: {e}")
    return False

def wait_turnstile_pass(sb: SB, timeout: int = TIMEOUT_WAIT_CF) -> bool:
    start = time.time()
    attempts = 0
    while time.time() - start < timeout:
        elapsed = int(time.time()-start)
        if _get_turnstile_hidden_value(sb) or _has_cf_clearance(sb):
            print(f"✅ Turnstile verified after {elapsed}s")
            return True
        if attempts < MAX_CLICK_TRIES:
            attempts += 1
            print(f"🔁 Attempt {attempts}/{MAX_CLICK_TRIES} clicking Turnstile...")
            try_click_turnstile(sb)
            screenshot(sb, f"turnstile_attempt_{attempts:02d}.png")
        human_sleep(2,4)
    print("❌ Turnstile verification timeout")
    screenshot(sb, "turnstile_timeout.png")
    return False

# =================================================
# 主流程
# =================================================
def main():
    if not SERVER_URL:
        raise ValueError("❌ WEIRDHOST_SERVER_URL not set")
    display = None
    if platform.system().lower()=="linux" and not os.environ.get("DISPLAY"):
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=False, size=(1920,1080))
            display.start()
            os.environ["DISPLAY"] = display.new_display_var
            print("🖥️ Xvfb started")
        except ImportError:
            print("⚠️ Install pyvirtualdisplay for Linux headless")
    try:
        chrome_args = ['--no-sandbox','--disable-blink-features=AutomationControlled','--window-size=1920,1080']
        with SB(uc=True, headless2=True, chromium_arg=' '.join(chrome_args), timeout=30) as sb:
            print("🌐 Visiting hub.weirdhost.xyz")
            sb.uc_open_with_reconnect("https://hub.weirdhost.xyz", reconnect_time=5)
            human_sleep(2,3)
            screenshot(sb, "00_homepage.png")
            if REMEMBER_WEB_COOKIE:
                sb.add_cookie({"name":"remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                               "value":REMEMBER_WEB_COOKIE,"domain":".weirdhost.xyz","path":"/","secure":True,"httpOnly":True,"sameSite":"Lax"})
                sb.refresh()
                human_sleep(2,3)
                screenshot(sb, "01_logged_in.png")
            print(f"🔗 Navigating to {SERVER_URL}")
            sb.uc_open_with_reconnect(SERVER_URL,reconnect_time=10)
            human_sleep(2,3)
            screenshot(sb, "02_server_page.png")
            # 点击续期按钮
            renewal_selectors = ['//button[.//span[contains(text(), "시간 추가")]]',
                                 '//button[contains(text(), "Renew")]']
            button_clicked = False
            for sel in renewal_selectors:
                if sb.is_element_visible(sel, timeout=5):
                    if _robust_click_with_retry(sb, sel, tries=3):
                        button_clicked=True
                        screenshot(sb,"03_after_renew_click.png")
                        break
            if not button_clicked:
                screenshot(sb,"renew_button_not_found.png")
                raise RuntimeError("❌ Could not click renewal button")
            print("🛡️ Waiting for Turnstile verification...")
            human_sleep(2,3)
            screenshot(sb,"04_before_turnstile.png")
            if wait_turnstile_pass(sb):
                print("✅ Turnstile passed!")
                screenshot(sb,"05_verification_passed.png")
                human_sleep(3,5)
                print("🎉 Auto-renewal completed successfully!")
            else:
                screenshot(sb,"06_verification_failed.png")
                raise RuntimeError("❌ Turnstile verification failed")
    except Exception as e:
        print(f"💥 Error: {e}")
        traceback.print_exc()
        if 'sb' in locals():
            screenshot(sb,"error_final.png")
        raise
    finally:
        if display:
            display.stop()
            print("🖥️ Xvfb stopped")

if __name__=="__main__":
    try:
        main()
        print("✨ Script finished successfully!")
    except Exception as e:
        print(f"💥 Script failed: {e}")
        exit(1)