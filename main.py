import os
import time
import random
import platform
from pathlib import Path
from seleniumbase import SB

# =================================================
# 配置区
# =================================================
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

SERVER_URL = os.environ.get("WEIRDHOST_SERVER_URL")
REMEMBER_WEB_COOKIE = os.environ.get("REMEMBER_WEB_COOKIE")

# 元素选择器
EXPIRY_SELECTOR = "p.sc-fFubgz.bjNVbG"  # 包含 '유통기한 2026-02-09...'
RENEW_BUTTON = "button.bkrtgq"           # '시간 추가' 按钮
TURNSTILE_IFRAME = "iframe[src*='turnstile']"

def human_sleep(a=1.0, b=2.0):
    time.sleep(random.uniform(a, b))

def get_expiry_text(sb):
    """抓取页面当前的到期时间"""
    try:
        if sb.is_element_visible(EXPIRY_SELECTOR):
            text = sb.get_text(EXPIRY_SELECTOR)
            return text.replace("유통기한", "").strip()
    except:
        return None
    return None

def main():
    if not SERVER_URL:
        print("❌ 错误: 未设置环境变量 WEIRDHOST_SERVER_URL")
        return

    with SB(uc=True, headless=False, locale="en") as sb:
        print("🚀 启动 Weirdhost 增强版续期脚本")
        
        # 1. 进入页面并登录
        sb.uc_open_with_reconnect(SERVER_URL, reconnect_time=5)
        
        if REMEMBER_WEB_COOKIE:
            sb.add_cookie({
                "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                "value": REMEMBER_WEB_COOKIE,
                "domain": "hub.weirdhost.xyz",
                "path": "/",
            })
            sb.refresh()
            human_sleep(2, 4)

        # 2. 记录续期前的时间
        old_time = get_expiry_text(sb)
        print(f"📅 续期前到期时间: {old_time}")

        # 3. 点击续期按钮
        if sb.is_element_visible(RENEW_BUTTON):
            print("🖱️ 点击 '시간 추가' 按钮...")
            sb.click(RENEW_BUTTON)
            human_sleep(2, 3)
        else:
            sb.save_screenshot("error_no_button.png")
            print("❌ 未找到续期按钮，请检查 Cookie 或页面状态")
            return

        # 4. 处理 Cloudflare Turnstile
        print("⏳ 等待 Turnstile 验证中...")
        start_wait = time.time()
        passed = False
        
        while time.time() - start_wait < 90:
            # 检查验证是否成功的硬指标：
            # A. 验证响应的隐藏 input 有值
            token = sb.get_attribute("input[name='cf-turnstile-response']", "value", timeout=1)
            if token and len(token) > 20:
                print("✅ Turnstile 验证码已自动/手动填入")
                passed = True
                break
            
            # B. 如果 iframe 还在，尝试模拟点击其中心位置
            if sb.is_element_visible(TURNSTILE_IFRAME):
                try:
                    # 获取坐标并点击
                    iframe = sb.find_element(TURNSTILE_IFRAME)
                    loc = iframe.location_once_scrolled_into_view
                    size = iframe.size
                    cx = int(loc['x'] + size['width'] * 0.2) # 偏左点击 checkbox
                    cy = int(loc['y'] + size['height'] * 0.5)
                    sb.uc_gui_click_x_y(cx, cy)
                    print("🔘 模拟点击 Turnstile Checkbox")
                except:
                    pass
            
            # C. 检查时间是否已经更新（有的页面验证后会自动刷新）
            current_time = get_expiry_text(sb)
            if current_time and current_time != old_time:
                print("✨ 检测到时间已更新，验证自动通过！")
                passed = True
                break
                
            time.sleep(4)

        # 5. 最终结果确认
        human_sleep(3, 5) # 给后端处理留点时间
        final_time = get_expiry_text(sb)
        
        print("-" * 30)
        if final_time and final_time != old_time:
            print(f"🎉 续期成功！")
            print(f"   原时间: {old_time}")
            print(f"   现时间: {final_time}")
            sb.save_screenshot("success_renew.png")
        else:
            print("❌ 续期失败：到期时间未发生变化")
            sb.save_screenshot("failed_renew.png")
            # 额外检查是否有报错信息
            if sb.is_text_visible("Wait"):
                print("⚠️ 提示: 续期请求过于频繁，请稍后再试")

if __name__ == "__main__":
    main()
