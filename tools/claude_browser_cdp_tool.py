"""Browser Chrome DevTools Protocol tool — advanced browser automation."""

import base64
import json

import logging

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from tools.registry import registry

# Schema for browser_cdp tool
BROWSER_CDP_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "Browser action to perform",
            "enum": [
                "navigate", "execute", "screenshot",
                "wait_selector", "get_cookies", "set_cookie",
                "network_monitor"
            ],
        },
        "url": {
            "type": "string",
            "description": "URL for navigate action",
        },
        "script": {
            "type": "string",
            "description": "JavaScript code for execute action",
        },
        "selector": {
            "type": "string",
            "description": "CSS selector for wait_selector or cookie name",
        },
        "value": {
            "type": "string",
            "description": "Cookie value or other context data",
        },
        "timeout_ms": {
            "type": "integer",
            "description": "Timeout in milliseconds",
            "default": 30000,
            "minimum": 1000,
            "maximum": 300000,
        },
    },
    "required": ["action"],
}


def browser_cdp(action, url=None, script=None, selector=None, value=None, timeout_ms=30000):
    """Advanced browser automation using Chrome DevTools Protocol."""
    
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "error": "Playwright not installed. Install with: pip install playwright && playwright install"
        }
    
    try:
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
    
    except Exception as e:
        return {"error": str(e)}


registry.register(
    name="browser_cdp",
    toolset="browser",
    schema=BROWSER_CDP_SCHEMA,
    handler=lambda args, **kw: browser_cdp(
        action=args.get("action", ""),
        url=args.get("url"),
        script=args.get("script"),
        selector=args.get("selector"),
        value=args.get("value"),
        timeout_ms=args.get("timeout_ms", 30000),
    ),
    check_fn=lambda: PLAYWRIGHT_AVAILABLE,
    emoji="🌐",
)
