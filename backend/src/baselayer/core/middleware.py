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
from baselayer.core.tenant_context import set_tenant_context, clear_tenant_context

logger = get_logger(__name__)

__all__ = [
    "RequestIDMiddleware",
    "LoggingMiddleware",
    "SecurityHeadersMiddleware",
    "TenantMiddleware",
    "RateLimitMiddleware",
]


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


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware for extracting and setting tenant context from requests.

    This middleware attempts to extract tenant_id from:
    1. Authorization header (JWT token claims) - authoritative when present
    2. X-Tenant-ID header (for testing/internal calls, or when there's no
       JWT to decode) - only used as a fallback

    The tenant context is then available throughout the request lifecycle
    for automatic database query filtering.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        """Extract tenant context and process request."""
        tenant_id = None

        # Method 1: From Authorization header (JWT token). Unlike the
        # standalone engines in this fleet (which have no real user auth
        # and so have no JWT to decode), baselayer's login flow already
        # issues real JWTs (TokenManager.create_access_token) carrying a
        # "tenant_id" claim as of this change - decode it here rather than
        # duplicating the token-parsing logic. A decode failure (missing/
        # expired/malformed token) is deliberately swallowed rather than
        # rejecting the request: this middleware only extracts tenant
        # context, it isn't the auth gate - a route's own
        # get_current_user dependency is what actually rejects bad tokens.
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            try:
                from baselayer.core.auth import TokenManager

                payload = TokenManager().verify_token(token, token_type="access")
                claim = payload.get("tenant_id")
                if claim:
                    tenant_id = uuid.UUID(claim)
                    logger.debug("Extracted tenant_id from JWT claim", tenant_id=str(tenant_id))
            except Exception as e:
                logger.debug("Could not extract tenant_id from Authorization header", error=str(e))

        # Method 2: From X-Tenant-ID header (for testing/internal calls,
        # or as a fallback when Method 1 found nothing)
        tenant_id_header = request.headers.get("X-Tenant-ID")
        if tenant_id is None and tenant_id_header:
            try:
                tenant_id = uuid.UUID(tenant_id_header)
                logger.debug("Extracted tenant_id from X-Tenant-ID header", tenant_id=str(tenant_id))
            except ValueError:
                logger.warning("Invalid tenant_id in X-Tenant-ID header", tenant_id_header=tenant_id_header)
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid tenant_id format in X-Tenant-ID header"},
                )
        
        # Set (or explicitly clear) the tenant context for this request.
        # ContextVar state can otherwise leak across requests that share
        # the same context chain if a request without a tenant header
        # simply left a prior request's tenant_id in place instead of
        # clearing it.
        if tenant_id:
            set_tenant_context(tenant_id)
        else:
            clear_tenant_context()

        # Process the request
        response = await call_next(request)

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
