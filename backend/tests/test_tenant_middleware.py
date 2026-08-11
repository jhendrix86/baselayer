"""
Verifies TenantMiddleware actually extracts tenant_id from a real JWT
(not just that the JWT-decoding code doesn't crash). Deliberately avoids
the db_session/client fixtures - Base.metadata.create_all() pulls in
every registered model including ones with Postgres-specific JSONB
columns that don't compile under this test suite's SQLite fallback (see
core/database.py's do_orm_execute listener docstring). None of that is
needed here: JWT creation/decoding and the middleware's context-setting
are pure Python, no database involved.

Every test is explicitly marked @pytest.mark.asyncio (matching
test_auth.py's existing convention) rather than relying on this repo's
pytest.ini asyncio_mode = auto - that setting is silently never applied,
since pytest.ini uses the wrong section header ([tool:pytest], which
only pytest reads from setup.cfg; a standalone pytest.ini needs [pytest])
so pytest falls back to strict mode. Confirmed directly: an unmarked
async test in this file fails with "async def functions are not
natively supported" before the marker was added. Not fixed here - the
same addopts block also carries --cov-fail-under=80/--strict-markers/
--strict-config, none of which are active today either, and flipping
the header on would activate all of them at once with an unassessed
blast radius well beyond this change's scope.
"""

import uuid

import pytest
from starlette.requests import Request
from starlette.responses import Response

from baselayer.core.auth import TokenManager
from baselayer.core.middleware import TenantMiddleware
from baselayer.core.tenant_context import clear_tenant_context, get_tenant_context


def _request_with_headers(headers: dict) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {"type": "http", "method": "GET", "path": "/", "headers": raw_headers, "query_string": b""}
    return Request(scope)


async def _call_next(request: Request) -> Response:
    return Response("ok")


@pytest.fixture(autouse=True)
def _reset_tenant_context():
    clear_tenant_context()
    yield
    clear_tenant_context()


@pytest.mark.asyncio
async def test_jwt_tenant_claim_sets_context():
    tenant_id = uuid.uuid4()
    token = TokenManager().create_access_token({
        "sub": str(uuid.uuid4()),
        "email": "a@example.com",
        "role": "user",
        "name": "A User",
        "tenant_id": str(tenant_id),
    })

    request = _request_with_headers({"Authorization": f"Bearer {token}"})
    await TenantMiddleware(app=None).dispatch(request, _call_next)

    assert get_tenant_context() == tenant_id


@pytest.mark.asyncio
async def test_jwt_without_tenant_claim_falls_back_to_no_context():
    """Tokens issued before this change (or for a user with no tenant_id) carry no claim at all."""
    token = TokenManager().create_access_token({
        "sub": str(uuid.uuid4()), "email": "a@example.com", "role": "user", "name": "A User",
    })

    request = _request_with_headers({"Authorization": f"Bearer {token}"})
    await TenantMiddleware(app=None).dispatch(request, _call_next)

    assert get_tenant_context() is None


@pytest.mark.asyncio
async def test_malformed_token_does_not_crash_and_falls_back_to_x_tenant_id():
    tenant_id = uuid.uuid4()
    request = _request_with_headers({
        "Authorization": "Bearer not-a-real-jwt",
        "X-Tenant-ID": str(tenant_id),
    })
    await TenantMiddleware(app=None).dispatch(request, _call_next)

    assert get_tenant_context() == tenant_id


@pytest.mark.asyncio
async def test_jwt_tenant_claim_takes_priority_over_x_tenant_id_header():
    jwt_tenant = uuid.uuid4()
    header_tenant = uuid.uuid4()
    token = TokenManager().create_access_token({
        "sub": str(uuid.uuid4()), "email": "a@example.com", "role": "user", "name": "A User",
        "tenant_id": str(jwt_tenant),
    })

    request = _request_with_headers({
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(header_tenant),
    })
    await TenantMiddleware(app=None).dispatch(request, _call_next)

    assert get_tenant_context() == jwt_tenant
