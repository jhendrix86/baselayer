# Multi-Tenancy Spec — Stage 4 Realignment (2026-08-10)

This replaces the informal spec Devin was working from. It exists because the
first pass (analytics-engine, content-engine committed; 7 more engines
partially done, uncommitted) added a `tenant_id` schema column and a context
variable everywhere, but nothing actually *enforces* tenant isolation. Read
this fully before writing any more code — the goal below is different from
"add tenant_id to models," which is the part that's already done everywhere.

## What's already true across the fleet (don't redo this part)

- `analytics-engine`, `content-engine`: committed and pushed. Have
  `app/models/tenant.py`, `app/models/tenant_base.py` (`TenantBase` mixin
  adding `tenant_id` FK, `nullable=False`), `app/middleware/tenant.py`,
  `app/tenant_context.py`, migrations. Models inherit `TenantBase`.
- `customer-support-engine`, `integration-engine`,
  `marketing-automation-engine`, `monitoring-engine`, `notification-engine`,
  `revenue-operations-engine`, `sales-engine`: uncommitted local work in the
  same shape, at varying stages of completeness. `integration-engine` in
  particular has an empty `app/middleware/__init__.py` with no `tenant.py`
  inside it yet — further along than "not started" but behind the other six.
- `governance-engine`, `baselayer`: untouched. Nothing to build on yet.

## The three real gaps (present in every engine touched so far)

### 1. Tenant identity is a spoofable client header

`app/middleware/tenant.py` (analytics-engine / content-engine version) reads
`X-Tenant-ID` directly off the incoming request with no verification. Any
caller can set that header to any UUID and read/write another tenant's data.
The JWT path in the same file is an explicit stub (`# JWT extraction not yet
implemented`).

**Fix**: derive tenant identity from the already-working `unkey-auth`
package (`unkey-auth/unkey_auth/`), not a raw header. `UnkeyClient.verify_key`
already fetches the full Unkey response into `VerifyKeyResult.raw` — Unkey
supports an `externalId` and `meta` on every key, either of which is a normal
place to carry a tenant id, but `VerifyKeyResult` currently only surfaces
`valid`, `code`, `key_id`, `ratelimits`. Do this in `unkey-auth` first (one
place, every engine gets it for free):

- Add `external_id: Optional[str]` and `meta: Dict[str, Any]` fields to
  `VerifyKeyResult` in `unkey-auth/unkey_auth/client.py`, populated from
  `data.get("externalId")` / `data.get("meta", {})`.
- In each engine's tenant middleware, call the existing `require_api_key`
  dependency first, then set tenant context from
  `result.external_id or result.meta.get("tenant_id")` — not from
  `X-Tenant-ID`. Keep `X-Tenant-ID` only as a fallback for local dev when
  `UNKEY_ROOT_KEY` is unset (matches unkey-auth's existing fail-open
  behavior), and log loudly when that fallback path is used.

### 2. Nothing actually filters queries by tenant

`app/tenant_context.py` (analytics-engine version) defines
`TenantQueryMixin.apply_tenant_filter()` and `get_tenant_aware_db()`, but a
repo-wide grep (`grep -rn "get_tenant_aware_db\|apply_tenant_filter" app/routers/
app/main.py`) shows neither is imported or called anywhere. The
`before_execute` event listener inside `get_tenant_aware_db()` is literally
`pass`. content-engine's version doesn't even have `TenantQueryMixin` —
just get/set/clear on a ContextVar that nothing reads. Net effect: every
list/get endpoint in both committed engines currently returns all tenants'
rows, unfiltered.

**Fix**: don't rely on every route remembering to call a filter helper —
that's what "not wired into app/routers/" already proved doesn't happen.
Use SQLAlchemy's `do_orm_execute` event with `with_loader_criteria` to make
filtering automatic and impossible to forget:

```python
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

@event.listens_for(AsyncSession, "do_orm_execute")
def _apply_tenant_filter(execute_state):
    tenant_id = get_tenant_context()
    if tenant_id is None or not execute_state.is_select:
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantBase,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )
```

Register this once per engine (e.g. in `app/database.py` next to
`AsyncSessionLocal`), not per-router. Delete the dead `get_tenant_aware_db`/
`apply_tenant_filter` code once this replaces it — don't leave both patterns
in the codebase.

### 3. Nothing populates tenant_id on create

`tenant_id` is `nullable=False` on every model via `TenantBase`, but no
create endpoint sets it — it depends entirely on the caller including it in
the request body. Against a real database this either violates the NOT NULL
constraint (if omitted) or lets a caller write into another tenant's data
(if they simply supply someone else's tenant_id in the body, since nothing
cross-checks it against their authenticated identity).

**Fix**: a SQLAlchemy `before_insert` mapper event on `TenantBase`, setting
`target.tenant_id` from context if unset, and *overwriting* it (not
trusting) if a value was already present but doesn't match the authenticated
tenant. Put this next to the `TenantBase` mixin definition so every model
that inherits it gets it automatically:

```python
from sqlalchemy import event

@event.listens_for(TenantBase, "before_insert", propagate=True)
def _set_tenant_id(mapper, connection, target):
    tenant_id = get_tenant_context()
    if tenant_id is not None:
        target.tenant_id = tenant_id
```

## Required proof of correctness, per engine

None of the above counts as done without a test that actually exercises
cross-tenant isolation — the previous status update ("validated and
working") had no such test anywhere in analytics-engine or content-engine.
Minimum per engine:

1. Create tenant A, create a record as tenant A.
2. Switch context to tenant B, list/get the same resource type — assert
   tenant A's record is **not** in the results.
3. Attempt to create a record as tenant B with tenant A's id spoofed into
   the request body — assert it's stored under tenant B's real id anyway.
4. Omit tenant_id entirely on create — assert it's populated from context,
   not left null.

## Recommended order of work

Don't repeat the flawed pattern across the remaining 7 engines and then fix
all 9 at once. Fix it in one place first:

1. `unkey-auth`: add `external_id`/`meta` to `VerifyKeyResult`. Small,
   isolated, unblocks everything else.
2. `analytics-engine`: already has the most scaffolding built — retrofit
   points 1-3 above, add the isolation tests, get it fully green. This
   becomes the reference implementation.
3. `content-engine`: apply the same corrected pattern (it's missing more of
   the scaffolding than analytics-engine, so this also proves the pattern
   works from a colder start).
4. Only after 2-3 are verified working: apply the corrected pattern to the
   7 partially-done engines (customer-support, integration, marketing-
   automation, monitoring, notification, revenue-operations, sales) and the
   2 untouched ones (governance, baselayer itself does not need this — it
   has no tenant-scoped data model, skip it).

Commit incrementally per engine, as before. Push each engine's own repo
directly — don't wait to batch everything into one giant commit.
