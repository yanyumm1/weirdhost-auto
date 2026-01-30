#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright, TimeoutError, expect


class WeirdhostAuto:
    def __init__(self):
        self.url = os.getenv('WEIRDHOST_URL', 'https://hub.weirdhost.xyz')
        self.server_urls = os.getenv('WEIRDHOST_SERVER_URLS', '')
        self.login_url = os.getenv('WEIRDHOST_LOGIN_URL', 'https://hub.weirdhost.xyz/auth/login')

        self.remember_web_cookie = os.getenv('REMEMBER_WEB_COOKIE', '')
        self.email = os.getenv('WEIRDHOST_EMAIL', '')
        self.password = os.getenv('WEIRDHOST_PASSWORD', '')

        self.headless = os.getenv('HEADLESS', 'true').lower() == 'true'
        self.slow_mo = int(os.getenv('SLOW_MO', '100'))

        self.server_list = []
        if self.server_urls:
            self.server_list = [url.strip() for url in self.server_urls.split(',') if url.strip()]

        self.server_results = {}
    
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {level}: {message}")
    
    def has_cookie_auth(self):
        return bool(self.remember_web_cookie)
    
    def has_email_auth(self):
        return bool(self.email and self.password)
    
    def check_login_status(self, page):
        try:
            self.log("检查登录状态...")
            if "login" in page.url or "auth" in page.url:
                self.log("当前在登录页面，未登录")
                return False
            else:
                self.log("不在登录页面，判断为已登录")
                return True
                
        except Exception as e:
            self.log(f"检查登录状态时出错: {e}", "ERROR")
            return False
    
    def login_with_cookies(self, context):
        try:
            self.log("尝试使用 Cookies 登录...")

            session_cookie = {
                'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                'value': self.remember_web_cookie,
                'domain': 'hub.weirdhost.xyz',
                'path': '/',
                'expires': int(time.time()) + 3600 * 24 * 365,
                'httpOnly': True,
                'secure': True,
                'sameSite': 'Lax'
            }
            
            context.add_cookies([session_cookie])
            self.log("已添加 remember_web cookie")
            return True
                
        except Exception as e:
            self.log(f"设置 Cookies 时出错: {e}", "ERROR")
            return False
    
    def login_with_email(self, page):
        try:
            self.log("尝试使用邮箱密码登录...")
            self.log(f"访问登录页面: {self.login_url}")
            page.goto(self.login_url, wait_until="domcontentloaded")
            email_selector = 'input[name="username"]'
            password_selector = 'input[name="password"]'
            login_button_selector = 'button[type="submit"]'
            self.log("等待登录表单元素加载...")
            page.wait_for_selector(email_selector)
            page.wait_for_selector(password_selector)
            page.wait_for_selector(login_button_selector)
            self.log("填写邮箱和密码...")
            page.fill(email_selector, self.email)
            time.sleep(1)
            page.fill(password_selector, self.password)
            time.sleep(1)
            self.log("点击登录按钮...")
            with page.expect_navigation(wait_until="domcontentloaded", timeout=90000):
                page.click(login_button_selector)
            if "login" in page.url or "auth" in page.url:
                self.log("邮箱密码登录失败，仍在登录页面", "ERROR")
                return False
            else:
                self.log("邮箱密码登录成功！")
                return True
                
        except Exception as e:
            self.log(f"邮箱密码登录时出错: {e}", "ERROR")
            return False
    
    def handle_cf_challenge(self, page, server_id):
        try:
            self.log(f"检查服务器 {server_id} 是否遇到CF挑战...")
            cf_selectors = [
                '#challenge-form',
                '.challenge-form',
                '#challenge-running',
                '#cf-content',
                '#challenge-stage',
                'text=Checking your browser'
            ]
            
            for selector in cf_selectors:
                try:
                    if page.locator(selector).is_visible(timeout=3000):
                        self.log(f"⚠️ 服务器 {server_id} 检测到CF挑战，正在等待...")

                        wait_time = 10
                        self.log(f"等待 {wait_time} 秒让CF挑战完成...")
                        time.sleep(wait_time)

                        if page.locator(selector).is_visible(timeout=3000):
                            self.log(f"⚠️ 服务器 {server_id} CF挑战仍然存在，继续等待...")
                            time.sleep(5)
                        
                        self.log(f"✅ 服务器 {server_id} CF挑战处理完成")
                        return True
                except:
                    continue

            cf_texts = ["Checking your browser", "Verify", "Security Check", "Cloudflare"]
            page_text = page.content().lower()
            
            for text in cf_texts:
                if text.lower() in page_text:
                    self.log(f"⚠️ 服务器 {server_id} 检测到CF相关文本，等待挑战...")
                    time.sleep(10)
                    return True
            
            return False
            
        except Exception as e:
            self.log(f"检查CF挑战时出错: {e}", "WARNING")
            return False
    
    def wait_for_page_ready(self, page, server_id, operation="操作"):
        self.log(f"等待服务器 {server_id} {operation}页面加载...")
        self.handle_cf_challenge(page, server_id)
        try:
            page.wait_for_selector('.server-details, .server-info, .card, .panel, .container, main, article', timeout=15000)
            self.log(f"✅ 服务器 {server_id} 主要内容已加载")
        except:
            self.log(f"⚠️ 服务器 {server_id} 未找到主要内容区域")
        try:
            page.wait_for_load_state('networkidle', timeout=20000)
            self.log(f"✅ 服务器 {server_id} 网络空闲")
        except:
            self.log(f"⚠️ 服务器 {server_id} 网络未完全空闲")
        time.sleep(3)
        self.handle_cf_challenge(page, server_id)
    
    def find_renew_button(self, page, server_id):
        selectors = [
            'button:has-text("시간추가")',      # 没有空格
            'button:has-text("시간 추가")',     # 有空格
            '//button[contains(text(), "시간추가")]',
            '//button[contains(text(), "시간 추가")]',
        ]
        
        time.sleep(2)
        
        self.log(f"🔍 服务器 {server_id} 开始查找续期按钮...")
        
        for selector in selectors:
            try:
                if selector.startswith('//'):
                    button = page.locator(f'xpath={selector}')
                else:
                    button = page.locator(selector)
                
                button.wait_for(state='visible', timeout=8000)
                
                if button.is_visible():
                    # 获取详细按钮信息
                    button_text = button.text_content().strip()
                    is_enabled = button.is_enabled()
                    is_disabled = button.is_disabled()
                    
                    self.log(f"✅ 服务器 {server_id} 找到按钮:")
                    self.log(f"   选择器: {selector}")
                    self.log(f"   实际文本: '{button_text}'")
                    self.log(f"   是否启用: {is_enabled}")
                    self.log(f"   是否禁用: {is_disabled}")
                    
                    # 检查按钮的HTML属性
                    button_html = button.evaluate('(element) => element.outerHTML')
                    self.log(f"   按钮HTML: {button_html[:200]}...")
                    
                    return button
                    
            except Exception as e:
                self.log(f"选择器 {selector} 查找失败: {str(e)[:100]}")
                continue
        
        # 如果上面没找到，尝试更精确的查找
        self.log(f"服务器 {server_id} 常规选择器未找到，尝试精确查找...")
        return self.find_button_exact_match(page, server_id)
    
    def find_button_exact_match(self, page, server_id):
        """精确查找按钮，确保匹配正确的按钮"""
        try:
            self.log(f"服务器 {server_id} 开始精确查找所有按钮...")
            
            # 获取页面上所有按钮
            all_buttons = page.locator('button')
            button_count = all_buttons.count()
            self.log(f"找到 {button_count} 个按钮元素")
            
            target_texts = ["시간추가", "시간 추가"]
            
            for i in range(button_count):
                try:
                    button = all_buttons.nth(i)
                    if button.is_visible():
                        text = button.text_content().strip()
                        
                        self.log(f"按钮 {i}: 文本='{text}'")
                        
                        # 检查是否完全匹配目标文本
                        for target in target_texts:
                            if text == target:
                                self.log(f"✅ 服务器 {server_id} 精确匹配到按钮: '{text}'")
                                
                                # 验证按钮属性
                                tag_name = button.evaluate('(element) => element.tagName')
                                button_type = button.get_attribute('type') or 'button'
                                onclick = button.get_attribute('onclick') or '无'
                                
                                self.log(f"   标签名: {tag_name}")
                                self.log(f"   类型: {button_type}")
                                self.log(f"   onclick: {onclick[:100]}")
                                
                                return button
                except:
                    continue
            
            # 如果按钮在 <a> 标签中
            all_links = page.locator('a')
            link_count = all_links.count()
            self.log(f"找到 {link_count} 个链接元素")
            
            for i in range(min(link_count, 50)):  # 最多检查50个
                try:
                    link = all_links.nth(i)
                    if link.is_visible():
                        text = link.text_content().strip()
                        
                        for target in target_texts:
                            if text == target:
                                self.log(f"✅ 服务器 {server_id} 在链接中找到按钮: '{text}'")
                                return link
                except:
                    continue
                    
        except Exception as e:
            self.log(f"精确查找失败: {e}")
        
        return None
    
    def find_start_button(self, page, server_id):
        selectors = [
            'button:has-text("Start")',
            '//button[text()="Start"]',
            'button:has-text("Start Server")',
            'button:has-text("시작")',
            '//button[contains(text(), "Start")]',
        ]
        
        for selector in selectors:
            try:
                if selector.startswith('//'):
                    button = page.locator(f'xpath={selector}')
                else:
                    button = page.locator(selector)

                button.wait_for(state='visible', timeout=8000)
                
                if button.is_visible():
                    self.log(f"✅ 服务器 {server_id} 找到启动按钮: {selector}")
                    return button
                    
            except Exception as e:
                continue

        return self.find_button_alternative_methods(page, server_id, ["Start", "시작"], exact_match=True)
    
    def find_button_alternative_methods(self, page, server_id, keywords, exact_match=False):
        try:
            all_buttons = page.locator('button')
            button_count = all_buttons.count()
            
            for i in range(button_count):
                try:
                    button = all_buttons.nth(i)
                    if button.is_visible():
                        text = button.text_content().strip()
                        
                        if exact_match:
                            if any(keyword == text for keyword in keywords):
                                self.log(f"✅ 服务器 {server_id} 通过文本搜索找到按钮: '{text}'")
                                return button
                        else:
                            if any(keyword in text for keyword in keywords):
                                self.log(f"✅ 服务器 {server_id} 通过文本搜索找到按钮: '{text}'")
                                return button
                except:
                    continue
        except:
            pass

        try:
            primary_buttons = page.locator('button.btn-primary, button.btn-success, button.btn-info, button.is-primary, .btn, .button')
            if primary_buttons.count() > 0:
                for i in range(primary_buttons.count()):
                    button = primary_buttons.nth(i)
                    if button.is_visible():
                        text = button.text_content().strip()
                        
                        if exact_match:
                            if any(keyword == text for keyword in keywords):
                                self.log(f"✅ 服务器 {server_id} 通过class找到按钮")
                                return button
                        else:
                            if any(keyword in text for keyword in keywords):
                                self.log(f"✅ 服务器 {server_id} 通过class找到按钮")
                                return button
        except:
            pass
        
        self.log(f"❌ 服务器 {server_id} 所有方法都未找到按钮")
        return None
    
    def check_renewal_status(self, page, server_id):
        """检查服务器当前状态，确定是否需要续期"""
        try:
            self.log(f"服务器 {server_id} 检查续期状态...")
            
            # 查找剩余时间显示
            time_indicators = [
                '剩余时间',
                '남은 시간',
                'remaining',
                'expires',
                '만료',
                '시간 남음'
            ]
            
            page_text = page.content()
            
            for indicator in time_indicators:
                if indicator in page_text:
                    # 尝试提取时间信息
                    self.log(f"找到时间指示器: {indicator}")
                    
                    # 查找附近的文本
                    try:
                        # 使用更智能的方式查找时间
                        time_elements = page.locator(f'text=/{indicator}.*/i')
                        if time_elements.count() > 0:
                            for i in range(time_elements.count()):
                                element_text = time_elements.nth(i).text_content()
                                self.log(f"时间信息 {i}: {element_text}")
                    except:
                        pass
            
            # 检查是否有"已续期"或"今日已续期"的提示
            renewed_indicators = ["이미 추가", "오늘 추가", "already renewed", "오늘은 더 이상"]
            
            for indicator in renewed_indicators:
                if indicator in page_text:
                    self.log(f"ℹ️ 服务器 {server_id} 检测到已续期提示: {indicator}")
                    return "already_renewed_today"
            
            return "can_renew"
            
        except Exception as e:
            self.log(f"检查续期状态出错: {e}")
            return "unknown"
    
    def renew_server(self, page, server_url):
        try:
            server_id = server_url.split('/')[-1]
            self.log(f"📅 开始续期服务器 {server_id}")
            
            # 多次尝试访问页面
            for attempt in range(3):
                try:
                    self.log(f"尝试 {attempt+1}/3 访问服务器页面")
                    page.goto(server_url, wait_until="networkidle", timeout=30000)
                    break
                except:
                    if attempt == 2:
                        raise
                    time.sleep(5)
            
            # 等待更长时间确保页面加载
            time.sleep(5)
            self.wait_for_page_ready(page, server_id, "续期")
            
            # 检查页面是否正常显示
            page_title = page.title()
            self.log(f"页面标题: {page_title}")
            
            # 检查是否有错误信息
            error_indicators = ["error", "404", "not found", "오류", "에러"]
            page_content = page.content().lower()
            if any(indicator in page_content for indicator in error_indicators):
                self.log(f"⚠️ 服务器 {server_id} 页面可能包含错误")
            
            # 查找续期按钮
            button = self.find_renew_button(page, server_id)
            
            if not button:
                # 尝试不同的查找策略
                self.log(f"服务器 {server_id} 首次查找未找到按钮，尝试备用方法...")
                
                # 方法1：通过数据属性查找
                try:
                    button = page.locator('[data-action="renew"], [data-test="renew-button"]').first
                    if button.is_visible(timeout=3000):
                        self.log(f"✅ 通过data属性找到按钮")
                except:
                    pass
                
                # 方法2：通过CSS类名查找
                if not button:
                    try:
                        button_classes = ['renew-button', 'btn-renew', 'add-time', 'time-add', '시간추가']
                        for class_name in button_classes:
                            try:
                                button = page.locator(f'.{class_name}').first
                                if button.is_visible(timeout=3000):
                                    self.log(f"✅ 通过CSS类名找到按钮: {class_name}")
                                    break
                            except:
                                continue
                    except:
                        pass
            
            if not button:
                self.log(f"❌ 服务器 {server_id} 未找到续期按钮，保存页面用于调试")
                
                # 在headless模式下也保存截图
                try:
                    screenshot_path = f"error_{server_id}_{int(time.time())}.png"
                    page.screenshot(path=screenshot_path, full_page=True)
                    self.log(f"📸 错误截图已保存: {screenshot_path}")
                except:
                    pass
                    
                return "no_renew_button"
            
            # 检查按钮状态
            is_disabled = button.is_disabled()
            is_hidden = not button.is_visible()
            
            self.log(f"按钮状态 - 禁用: {is_disabled}, 隐藏: {is_hidden}")
            
            if is_disabled:
                self.log(f"服务器 {server_id} 按钮被禁用，检查原因...")
                
                # 检查是否有提示信息
                try:
                    disabled_reason = page.locator('.disabled-reason, .tooltip, .error-message').first
                    if disabled_reason.is_visible():
                        reason_text = disabled_reason.text_content()
                        self.log(f"禁用原因: {reason_text}")
                except:
                    pass
                
                return "renew_button_disabled"
            
            # 执行点击
            self.log(f"✅ 服务器 {server_id} 准备点击续期按钮")
            
            # 尝试不同的点击方式
            click_result = self.click_renew_button_and_check(page, button, server_id)
            
            return click_result
                
        except Exception as e:
            self.log(f"❌ 服务器 {server_id} 续期过程中出错: {str(e)}")
            import traceback
            self.log(f"错误详情: {traceback.format_exc()}", "ERROR")
            return "renew_error"
    
    def click_renew_button_and_check(self, page, button, server_id):
        try:
            # 截图点击前状态
            if not self.headless:
                page.screenshot(path=f"before_click_{server_id}.png")
            
            # 检查按钮状态
            is_enabled = button.is_enabled()
            is_visible = button.is_visible()
            
            self.log(f"服务器 {server_id} 点击前检查:")
            self.log(f"   按钮是否可见: {is_visible}")
            self.log(f"   按钮是否可用: {is_enabled}")
            
            if not is_enabled:
                # 尝试找出为什么禁用
                self.log(f"服务器 {server_id} 按钮被禁用，检查原因...")
                
                # 检查父元素是否禁用
                parent_state = button.evaluate('''
                    (element) => {
                        let parent = element.parentElement;
                        while (parent) {
                            if (parent.disabled || parent.style.display === 'none' || parent.style.visibility === 'hidden') {
                                return {disabled: true, reason: '父元素限制'};
                            }
                            parent = parent.parentElement;
                        }
                        return {disabled: false, reason: '未知'};
                    }
                ''')
                self.log(f"父元素状态: {parent_state}")
                
                return "renew_button_disabled"
            
            # 记录当前URL（用于判断是否跳转）
            before_url = page.url
            self.log(f"点击前URL: {before_url}")
            
            # 记录当前页面内容（关键部分）
            try:
                main_content = page.locator('main, .container, .content').first
                before_content = main_content.text_content()[:500] if main_content.count() > 0 else ""
            except:
                before_content = ""
            
            # 执行点击（尝试多种方式）
            click_success = False
            
            # 方法1：普通点击
            try:
                self.log(f"尝试方法1: 普通点击")
                button.hover()
                time.sleep(1)
                
                # 使用 force=True 强制点击，即使元素被覆盖
                button.click(force=True)
                click_success = True
            except Exception as e1:
                self.log(f"方法1失败: {e1}")
                
                # 方法2：JavaScript点击
                try:
                    self.log(f"尝试方法2: JavaScript点击")
                    page.evaluate('(element) => element.click()', button)
                    click_success = True
                except Exception as e2:
                    self.log(f"方法2失败: {e2}")
                    
                    # 方法3：模拟点击事件
                    try:
                        self.log(f"尝试方法3: 触发点击事件")
                        button.dispatch_event('click')
                        click_success = True
                    except Exception as e3:
                        self.log(f"方法3失败: {e3}")
            
            if not click_success:
                return "renew_click_error"
            
            # 等待并检查结果
            self.log(f"点击完成，等待响应...")
            
            # 等待可能的网络请求
            time.sleep(8)
            
            # 处理可能的CF挑战
            self.handle_cf_challenge(page, server_id)
            
            # 检查URL是否变化
            after_url = page.url
            self.log(f"点击后URL: {after_url}")
            
            # 检查页面内容变化
            try:
                after_content = main_content.text_content()[:500] if main_content.count() > 0 else ""
                
                # 查找成功或失败的消息
                page_text = page.content().lower()
                
                # 成功的关键词（韩文和英文）
                success_keywords = [
                    "시간이 추가되었습니다",  # 时间已添加
                    "추가되었습니다",         # 已添加
                    "성공",                   # 成功
                    "success",
                    "added",
                    "시간 추가 완료"          # 时间添加完成
                ]
                
                # 失败的关键词
                failure_keywords = [
                    "이미 추가",              # 已经添加
                    "이미 연장",              # 已经延长
                    "이미 갱신",              # 已经更新
                    "already",
                    "only once",
                    "한번만",                 # 只能一次
                    "오늘은 더 이상"           # 今天不能再
                ]
                
                # 检查成功
                for keyword in success_keywords:
                    if keyword in page_text:
                        self.log(f"✅ 服务器 {server_id} 检测到成功消息: {keyword}")
                        return "renew_success"
                
                # 检查是否已续期
                for keyword in failure_keywords:
                    if keyword in page_text:
                        self.log(f"ℹ️ 服务器 {server_id} 检测到已续期消息: {keyword}")
                        return "already_renewed"
                
                # 如果URL变化，说明有跳转
                if before_url != after_url:
                    self.log(f"⚠️ 服务器 {server_id} 页面发生跳转: {before_url} -> {after_url}")
                    return "renew_url_changed"
                
                # 如果内容变化
                if before_content and after_content and before_content != after_content:
                    self.log(f"⚠️ 服务器 {server_id} 页面内容已变化")
                    return "renew_content_changed"
                
                # 检查是否有弹出框或消息
                try:
                    alerts = page.locator('.alert, .message, .notification, .toast, .modal')
                    if alerts.count() > 0:
                        alert_text = alerts.first.text_content()[:200]
                        self.log(f"检测到提示框: {alert_text}")
                        
                        # 检查提示内容
                        alert_lower = alert_text.lower()
                        if any(keyword in alert_lower for keyword in success_keywords):
                            return "renew_success"
                        elif any(keyword in alert_lower for keyword in failure_keywords):
                            return "already_renewed"
                except:
                    pass
                
                # 检查按钮状态是否变化
                try:
                    after_button = self.find_renew_button(page, server_id)
                    if after_button and not after_button.is_enabled():
                        self.log(f"✅ 服务器 {server_id} 按钮变为禁用状态，可能续期成功")
                        return "renew_success"
                except:
                    pass
                
                self.log(f"⚠️ 服务器 {server_id} 无明确结果")
                return "renew_no_change"
                
            except Exception as e:
                self.log(f"检查结果时出错: {e}")
                return "renew_unknown"
                
        except Exception as e:
            self.log(f"❌ 服务器 {server_id} 点击续期按钮时出错: {e}")
            return "renew_click_error"
    
    def attempt_button_click(self, page, button, server_id):
        """尝试多种点击方式"""
        click_methods = [
            ("直接点击", lambda: button.click()),
            ("JavaScript点击", lambda: page.evaluate("(element) => element.click()", button)),
            ("强制点击", lambda: button.dispatch_event('click')),
        ]
        
        for method_name, click_func in click_methods:
            try:
                self.log(f"尝试 {method_name}...")
                
                # 点击前截图
                if not self.headless:
                    page.screenshot(path=f"before_{method_name}_{server_id}.png")
                
                # 执行点击
                click_func()
                
                # 等待响应
                time.sleep(8)
                
                # 检查结果
                page_content = page.content().lower()
                
                # 检查成功标志
                success_indicators = [
                    "시간이 추가되었습니다",
                    "시간 추가 성공",
                    "successfully",
                    "추가됨",
                    "added",
                    "성공"
                ]
                
                if any(indicator in page_content for indicator in success_indicators):
                    self.log(f"✅ 服务器 {server_id} 续期成功 ({method_name})")
                    return "renew_success"
                
                # 检查是否已续期
                already_indicators = [
                    "already renewed",
                    "이미 추가",
                    "이미 연장",
                    "only once",
                    "한번만"
                ]
                
                if any(indicator in page_content for indicator in already_indicators):
                    self.log(f"ℹ️ 服务器 {server_id} 已续期过 ({method_name})")
                    return "already_renewed"
                    
            except Exception as e:
                self.log(f"❌ {method_name} 失败: {e}")
                continue
        
        return "renew_click_error"
    
    def start_server(self, page, server_url):
        try:
            server_id = server_url.split('/')[-1]
            self.log(f"🚀 开始启动服务器 {server_id}")

            page.reload(wait_until="networkidle")

            self.wait_for_page_ready(page, server_id, "启动")

            button = self.find_start_button(page, server_id)
            
            if not button:
                self.log(f"❌ 服务器 {server_id} 未找到Start按钮")
                return "no_start_button"

            if not button.is_enabled():
                self.log(f"⚠️ 服务器 {server_id} Start按钮不可点击，可能被CF屏蔽，等待后重试...")
                time.sleep(5)

                button = self.find_start_button(page, server_id)
                if not button or not button.is_enabled():
                    self.log(f"ℹ️ 服务器 {server_id} 已启动，按钮不可点击")
                    return "already_started"

            if button.is_enabled():
                self.log(f"✅ 服务器 {server_id} 可以启动，正在点击...")

                button.hover()
                time.sleep(1)
                button.click()

                time.sleep(8)

                self.handle_cf_challenge(page, server_id)

                try:
                    new_button = self.find_start_button(page, server_id)
                    if new_button and not new_button.is_enabled():
                        self.log(f"✅ 服务器 {server_id} 启动成功，按钮状态已变化")
                        return "start_success"
                    else:
                        page_content = page.content().lower()
                        if "started" in page_content or "running" in page_content or "启动" in page_content or "시작" in page_content:
                            self.log(f"✅ 服务器 {server_id} 启动成功")
                            return "start_success"
                        else:
                            self.log(f"⚠️ 服务器 {server_id} 启动操作完成，但状态未知")
                            return "start_unknown"
                except:
                    self.log(f"⚠️ 服务器 {server_id} 启动操作完成，无法验证状态")
                    return "start_unknown"
            else:
                self.log(f"ℹ️ 服务器 {server_id} 已启动，按钮不可点击")
                return "already_started"
                
        except Exception as e:
            self.log(f"❌ 服务器 {server_id} 启动过程中出错: {e}")
            return "start_error"
    
    def process_server(self, page, server_url):
        server_id = server_url.split('/')[-1] if server_url else "unknown"
        self.log(f"🔧 开始处理服务器 {server_id}")
        self.log(f"访问服务器页面: {server_url}")

        self.server_results[server_id] = {
            'renew_status': '未执行',
            'start_status': '未执行'
        }
        
        try:
            # 访问页面
            page.goto(server_url, wait_until="networkidle", timeout=30000)
            time.sleep(5)  # 额外等待
            
            # 处理CF挑战
            self.handle_cf_challenge(page, server_id)
            
            # 检查登录状态
            if not self.check_login_status(page):
                self.log(f"服务器 {server_id} 未登录", "WARNING")
                self.server_results[server_id]['renew_status'] = 'login_failed'
                self.server_results[server_id]['start_status'] = 'login_failed'
                return f"{server_id}: login_failed"
            
            # 第一步：检查续期状态
            renewal_status = self.check_renewal_status(page, server_id)
            self.log(f"服务器 {server_id} 续期状态: {renewal_status}")
            
            if renewal_status == "already_renewed_today":
                self.log(f"ℹ️ 服务器 {server_id} 今日已续期，跳过续期操作")
                self.server_results[server_id]['renew_status'] = 'already_renewed'
            else:
                # 执行续期
                self.log(f"第一步：执行续期操作")
                renew_result = self.renew_server(page, server_url)
                self.server_results[server_id]['renew_status'] = renew_result
            
            time.sleep(5)
            
            # 第二步：执行启动
            self.log(f"第二步：执行启动操作")
            start_result = self.start_server(page, server_url)
            self.server_results[server_id]['start_status'] = start_result

            combined_result = f"renew:{self.server_results[server_id]['renew_status']},start:{start_result}"
            self.log(f"✅ 服务器 {server_id} 处理完成: {combined_result}")
            
            return f"{server_id}: {combined_result}"
            
        except Exception as e:
            self.log(f"❌ 处理服务器 {server_id} 时出错: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            self.server_results[server_id]['renew_status'] = 'error'
            self.server_results[server_id]['start_status'] = 'error'
            return f"{server_id}: error"
    
    def run(self):
        self.log("开始 Weirdhost 自动续期和启动任务")

        has_cookie = self.has_cookie_auth()
        has_email = self.has_email_auth()
        
        self.log(f"Cookie 认证可用: {has_cookie}")
        self.log(f"邮箱密码认证可用: {has_email}")
        
        if not has_cookie and not has_email:
            self.log("没有可用的认证信息！", "ERROR")
            return ["error: no_auth"]

        if not self.server_list:
            self.log("未设置服务器URL列表！请设置 WEIRDHOST_SERVER_URLS 环境变量", "ERROR")
            return ["error: no_servers"]
        
        self.log(f"需要处理的服务器数量: {len(self.server_list)}")
        for i, server_url in enumerate(self.server_list, 1):
            self.log(f"服务器 {i}: {server_url}")
        
        results = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-web-security',
                        '--disable-features=site-per-process'
                    ]
                )

                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )

                page = context.new_page()
                page.set_default_timeout(120000)
                page.set_default_navigation_timeout(120000)
                
                login_success = False

                if has_cookie:
                    if self.login_with_cookies(context):
                        self.log("检查Cookie登录状态...")
                        page.goto(self.url, wait_until="domcontentloaded")

                        self.handle_cf_challenge(page, "登录检查")
                        
                        if self.check_login_status(page):
                            self.log("✅ Cookie 登录成功！")
                            login_success = True
                        else:
                            self.log("Cookie 登录失败，cookies 可能已过期", "WARNING")

                if not login_success and has_email:
                    if self.login_with_email(page):
                        self.log("检查邮箱密码登录状态...")
                        page.goto(self.url, wait_until="domcontentloaded")

                        self.handle_cf_challenge(page, "登录检查")
                        
                        if self.check_login_status(page):
                            self.log("✅ 邮箱密码登录成功！")
                            login_success = True

                if login_success:
                    for server_url in self.server_list:
                        result = self.process_server(page, server_url)
                        results.append(result)
                        self.log(f"服务器处理结果: {result}")

                        time.sleep(8)
                else:
                    self.log("❌ 所有登录方式都失败了", "ERROR")
                    results = ["login_failed"] * len(self.server_list)
                
                browser.close()
                return results
                
        except TimeoutError as e:
            self.log(f"操作超时: {e}", "ERROR")
            return ["error: timeout"] * len(self.server_list)
        except Exception as e:
            self.log(f"运行时出错: {e}", "ERROR")
            return ["error: runtime"] * len(self.server_list)
    
    def write_readme_file(self, results):
        try:
            beijing_time = datetime.now(timezone(timedelta(hours=8)))
            timestamp = beijing_time.strftime('%Y-%m-%d %H:%M:%S')

            status_messages = {
                "renew_success": "✅ 续期成功",
                "already_renewed": "🔄 已经续期过",
                "no_renew_button": "❌ 未找到续期按钮",
                "renew_button_disabled": "❌ 续期按钮不可用(可能被CF屏蔽)",
                "renew_unknown_changed": "⚠️ 续期页面变化但结果未知",
                "renew_no_change": "⚠️ 续期页面无变化",
                "renew_click_error": "💥 点击续期按钮出错",
                "renew_error": "💥 续期过程出错",
                "renew_url_changed": "🔗 页面发生跳转",
                "renew_content_changed": "📄 页面内容变化",
                "renew_unknown": "❓ 未知状态",

                "start_success": "✅ 启动成功",
                "already_started": "🔄 已经启动",
                "no_start_button": "❌ 未找到Start按钮",
                "start_unknown": "⚠️ 启动完成但状态未知",
                "start_error": "💥 启动过程出错",

                "login_failed": "❌ 登录失败",
                "error": "💥 运行出错",
                "未执行": "⏸️ 未执行",

                "error: no_auth": "❌ 无认证信息",
                "error: no_servers": "❌ 无服务器配置",
                "error: timeout": "⏰ 操作超时",
                "error: runtime": "💥 运行时错误"
            }

            readme_content = f"""# 自动续期和启动脚本

**最后运行时间**: `{timestamp}` (北京时间)

## 运行结果

| 服务器ID | 续期状态 | 启动状态 |
|----------|----------|----------|
"""

            for server_id, status in self.server_results.items():
                renew_msg = status_messages.get(status['renew_status'], f"❓ {status['renew_status']}")
                start_msg = status_messages.get(status['start_status'], f"❓ {status['start_status']}")
                readme_content += f"| `{server_id}` | {renew_msg} | {start_msg} |\n"

            if not self.server_results:
                for result in results:
                    if ":" in result and not result.startswith("error:"):
                        parts = result.split(":", 1)
                        server_id = parts[0].strip()
                        status = parts[1].strip() if len(parts) > 1 else "unknown"
                        status_msg = status_messages.get(status, f"❓ 未知状态 ({status})")
                        readme_content += f"| `{server_id}` | {status_msg} | N/A |\n"
                    else:
                        status_msg = status_messages.get(result, f"❓ 未知状态 ({result})")
                        readme_content += f"| 未知 | {status_msg} | N/A |\n"

            total_servers = len(self.server_list)
            successful_renews = sum(1 for s in self.server_results.values() 
                                  if s['renew_status'] in ['renew_success', 'already_renewed'])
            successful_starts = sum(1 for s in self.server_results.values() 
                                  if s['start_status'] in ['start_success', 'already_started'])
            
            readme_content += f"""
## 统计信息

- 总服务器数: {total_servers}
- 成功续期: {successful_renews}/{total_servers}
- 成功启动: {successful_starts}/{total_servers}

"""

            with open('README.md', 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            self.log("📝 README已更新")
            
        except Exception as e:
            self.log(f"写入README文件失败: {e}", "ERROR")


def main():
    """主函数"""
    print("🚀 Weirdhost 自动续期和启动脚本启动")
    print("=" * 50)

    auto = WeirdhostAuto()

    if not auto.has_cookie_auth() and not auto.has_email_auth():
        print("❌ 错误：未设置认证信息！")
        print("\n请在 GitHub Secrets 中设置以下任一组合：")
        print("\n方案1 - Cookie 认证：")
        print("REMEMBER_WEB_COOKIE: 你的cookie值")
        print("\n方案2 - 邮箱密码认证：")
        print("WEIRDHOST_EMAIL: 你的邮箱")
        print("WEIRDHOST_PASSWORD: 你的密码")
        print("\n推荐使用 Cookie 认证，更稳定可靠")
        sys.exit(1)

    if not auto.server_list:
        print("❌ 错误：未设置服务器URL列表！")
        print("\n请在 GitHub Secrets 中设置：")
        print("WEIRDHOST_SERVER_URLS: https://hub.weirdhost.xyz/server/服务器ID1,https://hub.weirdhost.xyz/server/服务器ID2")
        print("\n示例: https://hub.weirdhost.xyz/server/abc12345,https://hub.weirdhost.xyz/server/abc67890")
        sys.exit(1)
    
    print("🔧 配置检查通过")
    print(f"📋 服务器数量: {len(auto.server_list)}")
    print("⚠️  注意：此版本已针对CF五秒盾进行优化")
    print("=" * 50)

    results = auto.run()

    auto.write_readme_file(results)
    
    print("=" * 50)
    print("📊 运行结果汇总:")

    for server_id, status in auto.server_results.items():
        print(f"\n服务器: {server_id}")
        print(f"  续期: {status['renew_status']}")
        print(f"  启动: {status['start_status']}")

    total = len(auto.server_list)
    renew_success = sum(1 for s in auto.server_results.values() 
                       if s['renew_status'] in ['renew_success', 'already_renewed'])
    start_success = sum(1 for s in auto.server_results.values() 
                       if s['start_status'] in ['start_success', 'already_started'])
    
    print("\n" + "=" * 50)
    print(f"📈 统计信息:")
    print(f"  总服务器数: {total}")
    print(f"  续期成功率: {renew_success}/{total}")
    print(f"  启动成功率: {start_success}/{total}")
    print("=" * 50)

    if any("login_failed" in result or "error:" in result for result in results):
        print("❌ 任务有失败的情况！")
        sys.exit(1)
    else:
        print("🎉 自动续期和启动任务完成！")
        sys.exit(0)


if __name__ == "__main__":
    main()