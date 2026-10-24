"""Browser Chrome DevTools Protocol tool — advanced browser automation."""

import logging
import json
from typing import Any, Dict, Optional, List

from tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool(name="browser_cdp")
def browser_cdp(
    action: str,
    url: Optional[str] = None,
    script: Optional[str] = None,
    selector: Optional[str] = None,
    value: Optional[str] = None,
    timeout_ms: int = 30000,
) -> Dict[str, Any]:
    """
    Advanced browser automation using Chrome DevTools Protocol via Playwright.
    
    Supported actions:
    - navigate: Load a URL
    - execute: Run JavaScript and return result
    - screenshot: Capture page screenshot
    - wait_selector: Wait for element to appear
    - get_cookies: Retrieve all cookies
    - set_cookie: Set a cookie
    - network_monitor: Monitor network requests
    
    Args:
        action: Action to perform
        url: URL for navigate action
        script: JavaScript code for execute action
        selector: CSS selector for wait_selector
        value: Cookie value or other context-specific data
        timeout_ms: Timeout in milliseconds
    
    Returns:
        Dict with action results
    """
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                if action == "navigate":
                    if not url:
                        return {"error": "navigate action requires url"}
                    page.goto(url, timeout=timeout_ms)
                    return {
                        "action": "navigate",
                        "url": url,
                        "title": page.title(),
                        "success": True,
                    }
                
                elif action == "execute":
                    if not script:
                        return {"error": "execute action requires script"}
                    result = page.evaluate(script)
                    return {
                        "action": "execute",
                        "result": result,
                        "success": True,
                    }
                
                elif action == "screenshot":
                    screenshot = page.screenshot()
                    import base64
                    b64 = base64.b64encode(screenshot).decode("utf-8")
                    return {
                        "action": "screenshot",
                        "image_base64": b64,
                        "size_bytes": len(screenshot),
                    }
                
                elif action == "wait_selector":
                    if not selector:
                        return {"error": "wait_selector action requires selector"}
                    page.wait_for_selector(selector, timeout=timeout_ms)
                    return {
                        "action": "wait_selector",
                        "selector": selector,
                        "found": True,
                    }
                
                elif action == "get_cookies":
                    cookies = context.cookies()
                    return {
                        "action": "get_cookies",
                        "cookies": cookies,
                        "count": len(cookies),
                    }
                
                elif action == "set_cookie":
                    if not value:
                        return {"error": "set_cookie action requires value"}
                    cookie_name = selector or "test_cookie"
                    context.add_cookies([
                        {
                            "name": cookie_name,
                            "value": value,
                            "url": page.url,
                        }
                    ])
                    return {
                        "action": "set_cookie",
                        "name": cookie_name,
                        "set": True,
                    }
                
                elif action == "network_monitor":
                    # Start monitoring network
                    network_log = []
                    def log_request(request):
                        network_log.append({
                            "method": request.method,
                            "url": request.url,
                            "resource_type": request.resource_type,
                        })
                    
                    page.on("request", log_request)
                    if url:
                        page.goto(url, timeout=timeout_ms)
                    
                    return {
                        "action": "network_monitor",
                        "requests": network_log,
                        "count": len(network_log),
                    }
                
                else:
                    return {
                        "error": f"Unknown action: {action}",
                        "available_actions": [
                            "navigate", "execute", "screenshot",
                            "wait_selector", "get_cookies", "set_cookie",
                            "network_monitor"
                        ]
                    }
            
            finally:
                context.close()
                browser.close()
    
    except ImportError:
        return {
            "error": "Playwright not installed. Install with: pip install playwright && playwright install"
        }
    except Exception as e:
        return {"error": str(e)}
