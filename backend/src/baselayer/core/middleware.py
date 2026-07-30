"""
BaseLayer Middleware Stack

Provides request ID generation, logging, security headers, and other
cross-cutting concerns for the FastAPI application.
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from baselayer.core.logging import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add unique request IDs for distributed tracing.
    
    Each request gets a unique ID that's added to the response headers
    and available in the request state for logging correlation.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        """Add request ID and process request."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request/response logging.
    
    Logs request details, timing, and response status with request ID correlation.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        """Log request and response details."""
        start_time = time.time()
        
        # Extract request details
        method = request.method
        url = str(request.url)
        user_agent = request.headers.get("user-agent", "unknown")
        client_ip = request.client.host if request.client else "unknown"
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log request
        logger.info(
            "request_started",
            method=method,
            url=url,
            user_agent=user_agent,
            client_ip=client_ip,
            request_id=request_id,
        )
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Calculate response time
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                "request_completed",
                method=method,
                url=url,
                status_code=status_code,
                process_time_ms=round(process_time * 1000, 2),
                request_id=request_id,
            )
            
            # Add response time header
            response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
            
            return response
            
        except Exception as exc:
            process_time = time.time() - start_time
            
            # Log error
            logger.error(
                "request_failed",
                method=method,
                url=url,
                error=str(exc),
                process_time_ms=round(process_time * 1000, 2),
                request_id=request_id,
            )
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "request_id": request_id,
                },
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Adds various security headers for production deployment.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )
        
        # HSTS for production
        from baselayer.core.config import get_settings
        settings = get_settings()
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for basic rate limiting.
    
    Implements a simple in-memory rate limiter. In production,
    this should be replaced with Redis-based rate limiting.
    """
    
    def __init__(self, app, calls: int = 60, period: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            app: FastAPI application
            calls: Number of allowed calls per period
            period: Time period in seconds
        """
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        """Apply rate limiting to request."""
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean up old entries
        cutoff_time = current_time - self.period
        self.clients = {
            ip: requests for ip, requests in self.clients.items()
            if any(req_time > cutoff_time for req_time in requests)
        }
        
        # Check rate limit
        if client_ip in self.clients:
            recent_requests = [
                req_time for req_time in self.clients[client_ip]
                if req_time > cutoff_time
            ]
            
            if len(recent_requests) >= self.calls:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "retry_after": self.period,
                    },
                    headers={"Retry-After": str(self.period)},
                )
            
            self.clients[client_ip] = recent_requests + [current_time]
        else:
            self.clients[client_ip] = [current_time]
        
        return await call_next(request)
