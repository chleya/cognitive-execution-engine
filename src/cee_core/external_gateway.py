"""External tool gateway and webhook notification system.

Enables CEE to interact with external systems:
1. HTTP API calls to external services
2. Webhook notifications for events
3. Import/Export capabilities
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Callable
from urllib.parse import urljoin, urlparse

from .event_log import EventLog
from .events import Event
from .tool_executor import ToolExecutionContext, ToolExecutionResult


@dataclass(frozen=True)
class HTTPGatewayConfig:
    """Configuration for HTTP gateway."""
    base_url: str
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    allowed_domains: Optional[List[str]] = None
    rate_limit_per_minute: int = 60
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WebhookConfig:
    """Configuration for webhook delivery."""
    url: str
    events: List[str] = field(default_factory=lambda: ["*"])
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 10.0
    retry_count: int = 2


WebhookSender = Callable[[Dict[str, Any]], bool]


@dataclass(frozen=True)
class DefaultWebhookSender:
    """Default webhook sender using HTTP POST."""
    
    def __call__(self, payload: Dict[str, Any]) -> bool:
        try:
            import requests
            url = payload.get("url", "")
            headers = payload.get("headers", {})
            data = payload.get("data", {})
            timeout = payload.get("timeout", 10.0)
            
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=timeout,
            )
            return 200 <= response.status_code < 300
        except ImportError:
            return False
        except Exception:
            return False


@dataclass
class RateLimiter:
    """Simple sliding window rate limiter."""
    
    max_calls: int = 60
    window_seconds: float = 60.0
    _call_times: List[float] = field(default_factory=list)
    
    def is_allowed(self) -> bool:
        now = time.monotonic()
        self._call_times = [
            t for t in self._call_times
            if now - t < self.window_seconds
        ]
        
        if len(self._call_times) >= self.max_calls:
            return False
        
        self._call_times.append(now)
        return True


class HTTPGateway:
    """HTTP gateway for external API calls."""
    
    def __init__(self, config: HTTPGatewayConfig, event_log: Optional[EventLog] = None):
        self.config = config
        self.event_log = event_log
        self.rate_limiter = RateLimiter(
            max_calls=config.rate_limit_per_minute,
            window_seconds=60.0,
        )
        self._request_count = 0
        self._error_count = 0
    
    def _is_domain_allowed(self, url: str) -> bool:
        if not self.config.allowed_domains:
            return False

        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False

        for allowed_domain in self.config.allowed_domains:
            if hostname == allowed_domain:
                return True
            if hostname.endswith("." + allowed_domain):
                return True
        return False
    
    def execute_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        call_id: str = "external_call_0",
    ) -> Dict[str, Any]:
        """Execute HTTP request through gateway."""
        url = urljoin(self.config.base_url, path)
        
        if not self._is_domain_allowed(url):
            return {
                "status": "failed",
                "error": f"Domain not allowed: {url}",
            }
        
        if not self.rate_limiter.is_allowed():
            return {
                "status": "failed",
                "error": "Rate limit exceeded",
            }
        
        self._request_count += 1
        
        try:
            import requests
        except ImportError:
            return {
                "status": "failed",
                "error": "requests library not installed",
            }
        
        merged_headers = {**self.config.headers, **(headers or {})}
        
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = requests.request(
                    method=method.upper(),
                    url=url,
                    json=data,
                    headers=merged_headers,
                    timeout=self.config.timeout_seconds,
                )
                
                if self.event_log is not None:
                    self.event_log.append(Event(
                        event_type="gateway.http.request",
                        payload={
                            "call_id": call_id,
                            "method": method,
                            "url": url,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                        },
                        actor="http_gateway",
                    ))
                
                if 200 <= response.status_code < 300:
                    return {
                        "status": "succeeded",
                        "status_code": response.status_code,
                        "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                        "headers": dict(response.headers),
                        "call_id": call_id,
                    }
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay_seconds)
                        
            except Exception as e:
                last_error = str(e)
                self._error_count += 1
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay_seconds)
                continue
        
        return {
            "status": "failed",
            "error": last_error,
            "call_id": call_id,
        }
    
    def get(self, path: str, call_id: str = "external_get_0") -> Dict[str, Any]:
        """Execute GET request."""
        return self.execute_request("GET", path, call_id=call_id)
    
    def post(self, path: str, data: Dict[str, Any], call_id: str = "external_post_0") -> Dict[str, Any]:
        """Execute POST request."""
        return self.execute_request("POST", path, data=data, call_id=call_id)
    
    def put(self, path: str, data: Dict[str, Any], call_id: str = "external_put_0") -> Dict[str, Any]:
        """Execute PUT request."""
        return self.execute_request("PUT", path, data=data, call_id=call_id)
    
    def delete(self, path: str, call_id: str = "external_delete_0") -> Dict[str, Any]:
        """Execute DELETE request."""
        return self.execute_request("DELETE", path, call_id=call_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get gateway usage statistics."""
        return {
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "error_rate": self._error_count / self._request_count if self._request_count > 0 else 0,
            "rate_limiter_window": self.rate_limiter.window_seconds,
            "rate_limiter_max_calls": self.rate_limiter.max_calls,
        }


class WebhookDispatcher:
    """Dispatches webhook notifications for CEE events."""
    
    def __init__(
        self,
        webhooks: List[WebhookConfig],
        sender: Optional[WebhookSender] = None,
        event_log: Optional[EventLog] = None,
    ):
        self.webhooks = webhooks
        self.sender = sender or DefaultWebhookSender()
        self.event_log = event_log
        self._dispatch_count = 0
        self._success_count = 0
        self._failure_count = 0
    
    def _matches_webhook(self, event_type: str, webhook: WebhookConfig) -> bool:
        """Check if event matches webhook subscription."""
        if "*" in webhook.events:
            return True
        return event_type in webhook.events
    
    def dispatch(self, event: Event) -> Dict[str, Any]:
        """Dispatch event to matching webhooks."""
        results = []
        
        for webhook in self.webhooks:
            if not self._matches_webhook(event.event_type, webhook):
                continue
            
            payload = {
                "event_type": event.event_type,
                "payload": event.to_dict() if hasattr(event, 'to_dict') else {},
                "actor": event.actor,
                "timestamp": time.time(),
                "url": webhook.url,
                "headers": webhook.headers,
                "timeout": webhook.timeout_seconds,
            }
            
            success = False
            for attempt in range(webhook.retry_count + 1):
                success = self.sender(payload)
                if success:
                    break
                if attempt < webhook.retry_count:
                    time.sleep(0.5)
            
            self._dispatch_count += 1
            if success:
                self._success_count += 1
            else:
                self._failure_count += 1
            
            results.append({
                "webhook_url": webhook.url,
                "event_type": event.event_type,
                "success": success,
            })
        
        if self.event_log is not None and results:
            self.event_log.append(Event(
                event_type="webhook.dispatched",
                payload={
                    "event_type": event.event_type,
                    "webhook_count": len(results),
                    "success_count": sum(1 for r in results if r["success"]),
                },
                actor="webhook_dispatcher",
            ))
        
        return {
            "event_type": event.event_type,
            "dispatched_to": len(results),
            "results": results,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get webhook dispatch statistics."""
        return {
            "total_dispatched": self._dispatch_count,
            "total_success": self._success_count,
            "total_failure": self._failure_count,
            "success_rate": self._success_count / self._dispatch_count if self._dispatch_count > 0 else 0,
            "registered_webhooks": len(self.webhooks),
        }
