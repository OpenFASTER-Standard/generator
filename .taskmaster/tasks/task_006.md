# Task ID: 6

**Title:** Design and implement collaborative annotation platform with public/private visibility scopes

**Status:** pending

**Dependencies:** 1 ✓, 2 ✓, 3

**Priority:** low

**Description:** Build a Wikipedia-like governance and visibility layer on top of the existing annotation system (Tasks 1-3) that enables the same tool to serve both public regulatory annotations (open Wikipedia-style) and private organizational use (internal process mapping) through visibility scopes, starting deliberately narrow with admin-only editing.

**Details:**

## Overview

This task implements the product/governance layer that transforms the existing single-user annotation tool into a multi-tenant collaborative platform. The key architectural insight: **public vs private is a visibility scope on the same underlying data model, not a fork of the codebase**. A bank mapping its internal CSV format and the public annotating MiKaDiv-FM XSD both use identical Task 1 SHACL shapes, Task 2 transformations, and Task 3 UI generation — only who can see and edit differs.

**Ground Truth Prior Art** (proven collaborative annotation/knowledge platforms):
- **Wikipedia's governance evolution**: Started admin-only (2001), opened gradually with increasing sophistication (semi-protection 2005, pending changes 2010). Provides a real roadmap for phased capability rollout.
- **Wikidata's statement-level provenance**: Every claim has references + qualifiers, exactly like this system's existing `reference_model.Reference`. Confirms the existing citation model generalizes beyond regulatory docs.
- **OpenStreetMap's changeset model**: Every edit is part of a named changeset with author/comment, enabling rollback and audit without preventing concurrent work. Maps directly to the existing `references_catalog` revision-history model.
- **GitHub's repository visibility**: Public/private is a top-level scope on a repo, not a per-file or per-line setting. Informs where visibility lives in this system's data model.
- **Hypothesis (web annotation)**: Separates personal annotations from group-shared ones via explicit scope selection at creation time. Validates that annotation scope can be a creation-time choice, not inferred.

## Architecture

### Visibility Model

**Two orthogonal dimensions** (both required, independently useful):

1. **Workspace visibility** (coarse-grained, GitHub-like):
   - `public`: Anyone can read; controlled who can write
   - `private`: Only workspace members can read or write
   - Scoped at **workspace** level (analogous to a GitHub repo or OSM user), not per-fact-key or per-revision
   - A workspace owns a references catalog (Task 1's existing `references_catalog/catalog.py` model), a corpus root, and a reviews directory

2. **Edit permissions** (fine-grained, Wikipedia-like, phased rollout):
   - **Phase 1 (this task)**: Admin-only editing for all workspaces (public or private). Read-only for non-admins.
   - **Phase 2 (future)**: Registered-user editing with review queues (Wikipedia's "autoconfirmed" equivalent)
   - **Phase 3 (future)**: IP/anonymous suggestions (Wikipedia's full model)

**Critical separation**: A workspace's visibility (public/private) is independent of its edit permissions (admin-only/open). A public workspace can be admin-only (early Wikipedia), and a private workspace can allow all members to edit (internal wiki). Both axes are real, useful, and orthogonal.

### Data Model Extensions

**New `workspaces` table** (SQLite, new `platform/workspaces.db`):
```sql
CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,  -- slugified name, URL-safe (e.g. "mikadiv-fm-public")
    display_name TEXT NOT NULL,
    visibility TEXT NOT NULL CHECK(visibility IN ('public', 'private')),
    edit_policy TEXT NOT NULL CHECK(edit_policy IN ('admin_only', 'members', 'public_suggestions')),
    catalog_path TEXT NOT NULL UNIQUE,  -- absolute path to this workspace's references.json
    corpus_root TEXT NOT NULL,
    reviews_dir TEXT NOT NULL,
    created_at TEXT NOT NULL,  -- ISO timestamp
    created_by TEXT NOT NULL
);

CREATE TABLE workspace_members (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'member', 'viewer')),
    added_at TEXT NOT NULL,
    added_by TEXT NOT NULL,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX idx_members_user ON workspace_members(user_id);
CREATE INDEX idx_members_workspace ON workspace_members(workspace_id);
```

**No changes to `reference_model`, `references_catalog`, `staleness_sweep`, `review_*` modules** — they remain workspace-agnostic. The webapp layer resolves workspace → catalog_path, then calls existing functions unchanged.

### Authentication & Identity

**Phase 1 (admin-only editing)**:
- **Identity provider**: Reuse cloud-admin-box's existing Vaultwarden-backed pattern (see `/work/CLAUDE.md`'s Vaultwarden section) OR simple JWT with a preconfigured user list, operator's choice during implementation
- **No OAuth/SSO** in Phase 1 — small trusted group (5-10 people), explicitly not solving for hundreds of users yet
- **Sessions**: HTTP-only cookie, server-side session store (SQLite `sessions` table or in-memory dict for Phase 1 simplicity)
- **Authorization**: Middleware checks workspace visibility + user's role before allowing reads/writes

### Webapp Changes (`webapp/app.py` extensions)

**New routes**:
```python
# Workspace management (admin-only in Phase 1)
POST   /api/workspaces                    # Create workspace
GET    /api/workspaces                    # List visible workspaces (public + user's private)
GET    /api/workspaces/{id}               # Workspace detail
PATCH  /api/workspaces/{id}               # Update workspace settings (admin-only)
DELETE /api/workspaces/{id}               # Delete workspace (admin-only)

POST   /api/workspaces/{id}/members       # Add member (admin-only)
DELETE /api/workspaces/{id}/members/{uid} # Remove member (admin-only)
GET    /api/workspaces/{id}/members       # List members

# Auth (simple, not OAuth)
POST   /api/auth/login                    # Username/password → session cookie
POST   /api/auth/logout                   # Clear session
GET    /api/auth/me                       # Current user info

# Existing routes gain workspace scoping:
GET    /api/{workspace_id}/pages          # was /api/pages
GET    /api/{workspace_id}/pages/{key}    # was /api/pages/{key}
POST   /api/{workspace_id}/citations      # was /api/citations
GET    /api/{workspace_id}/candidates     # was /api/candidates
GET    /api/{workspace_id}/review         # was /api/review
POST   /api/{workspace_id}/reviews        # was /api/reviews
```

**Authorization middleware**:
```python
async def check_workspace_access(
    workspace_id: str,
    user: Optional[User],
    required_permission: Literal["read", "write", "admin"]
) -> Workspace:
    workspace = get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(404)
    
    # Public workspace: anyone can read
    if workspace.visibility == "public" and required_permission == "read":
        return workspace
    
    # Private or write/admin: must be authenticated
    if user is None:
        raise HTTPException(401)
    
    # Check membership
    membership = get_membership(workspace_id, user.id)
    if membership is None:
        raise HTTPException(403, "Not a workspace member")
    
    # Phase 1: only admins can write
    if required_permission in ("write", "admin"):
        if workspace.edit_policy == "admin_only" and membership.role != "admin":
            raise HTTPException(403, "Admin-only editing enabled")
    
    if required_permission == "admin" and membership.role != "admin":
        raise HTTPException(403, "Admin role required")
    
    return workspace
```

### Frontend Changes (`webapp/frontend/`)

**New views**:
1. **Workspace selector/switcher** (`/`) — lists public + user's private workspaces, replaces current index
2. **Workspace detail** (`/w/{id}`) — shows workspace settings, members (if admin), link to pages/candidates/review
3. **Workspace settings** (`/w/{id}/settings`) — admin-only, edit visibility/edit_policy, manage members
4. **Login page** (`/login`) — simple username/password form
5. **Updated existing views** — all scoped under `/w/{workspace_id}/pages`, `/w/{workspace_id}/add`, `/w/{workspace_id}/review`

**Visual indicators** (using `@openfaster-standard/ui` components):
- Badge on workspace name showing visibility (public/private) and edit policy (read-only/admin-only/open)
- "You are viewing as: [username]" or "Not logged in" in header
- Disabled state on edit buttons for read-only users (Phase 1: all non-admins)

### Migration Path (Existing Data)

**Bootstrap script** (`platform/bootstrap_workspace.py`):
```python
"""One-time migration: wraps existing /work/ontologies/mikadiv-fm catalog
into a 'mikadiv-fm-public' workspace."""

def bootstrap_default_workspace():
    workspace_id = "mikadiv-fm-public"
    workspace = Workspace(
        id=workspace_id,
        display_name="MiKaDiv-FM (Public)",
        visibility="public",
        edit_policy="admin_only",  # Phase 1 default
        catalog_path="/work/ontologies/mikadiv-fm/references.json",
        corpus_root="/work/ontologies/mikadiv-fm/sources",
        reviews_dir="/work/ontologies/mikadiv-fm/reviews",
        created_at=datetime.now(timezone.utc).isoformat(),
        created_by="system"
    )
    insert_workspace(workspace)
    
    # Add initial admin (from env var or config)
    add_workspace_member(
        workspace_id=workspace_id,
        user_id=os.environ["INITIAL_ADMIN_USER"],
        role="admin",
        added_by="system"
    )
```

**No data loss**: Existing `/work/ontologies/mikadiv-fm/references.json` stays exactly where it is, with zero format changes. Only the webapp's routing layer changes to scope it under a workspace.

## Implementation Phases

### Phase A: Authentication & Workspace Data Model (foundation)
1. Add `platform/workspaces.db` schema
2. Implement simple login/logout (username/password, no OAuth yet)
3. Implement workspace CRUD operations
4. Write bootstrap script for existing mikadiv-fm catalog
5. Unit tests for workspace access control logic

### Phase B: Webapp Authorization Layer
1. Add workspace-scoped routing (`/api/{workspace_id}/*`)
2. Implement authorization middleware
3. Update all existing endpoints to check workspace access
4. Keep old routes (`/api/pages`) as redirects to default workspace (backward compat during development)

### Phase C: Frontend Multi-Workspace UI
1. Add login view
2. Add workspace selector/switcher view
3. Add workspace settings view (admin-only)
4. Update all existing views to be workspace-scoped
5. Add visual permission indicators (badges, disabled states)
6. Frontend tests for workspace navigation flows

### Phase D: End-to-End Verification & Documentation
1. Create second workspace (private) and verify isolation
2. Test permission boundaries (public read, private read, admin write, non-admin blocked)
3. Update README with multi-workspace setup instructions
4. Document API changes and migration path

## Real-World Use Cases (Validation)

**Public workspace** ("mikadiv-fm-public"):
- Visibility: public
- Edit policy: admin_only (Phase 1)
- Corpus: `/work/ontologies/mikadiv-fm/sources`
- Use case: Openly-curated MiKaDiv-FM annotations, like Wikipedia for regulatory schemas

**Private workspace** ("acme-bank-internal"):
- Visibility: private
- Edit policy: admin_only (Phase 1), later members (Phase 2)
- Corpus: `/work/acme-bank/proprietary-csv-specs/`
- Use case: Acme Bank mapping their internal CSV payroll format using the same SHACL/transformation tooling

Both workspaces:
- Use identical `reference_model.Reference` for citations
- Use identical `staleness_sweep` for drift detection
- Use identical Task 3 UI generation from SHACL shapes
- Differ only in visibility scope and member list

## Dependencies on Tasks 1-3

**Task 1 (RDF+SHACL model)** is required because:
- The annotation model must be proven general enough to handle both regulatory XSD (public) and arbitrary CSV/internal formats (private)
- Task 1's layer 1/layer 2 separation already validates this generality

**Task 2 (Transformation layer)** is required because:
- Private workspaces need the same declarative transformations (e.g., internal CSV → generated documentation) as public ones
- Can't validate "same tool, different scope" without the transformation layer actually working

**Task 3 (UI generation)** is required because:
- Form/table generation from SHACL shapes must work for both public regulatory shapes and private internal ones
- A private workspace creating a shape-driven form is the litmus test for generality

**Why cross-cutting, not earlier**: The existing `generator` codebase (reference_model, catalog, review workflow) was deliberately built workspace-agnostic. Adding workspace scoping before proving the core model works would be premature architecture. Now that Tasks 1-3 establish the foundation, this layer wraps it without modifying it.

## Non-Goals (Explicit Boundaries)

- **No federated workspaces** (ActivityPub, cross-instance): Single deployment, multiple workspaces, not distributed
- **No workspace-level corpus versioning beyond existing git**: Workspaces point to corpus directories; versioning is still git-based per existing pattern
- **No fine-grained ACLs** (per-page, per-revision): Workspace membership is all-or-nothing for Phase 1
- **No billing/metering**: Not a SaaS product, no usage limits
- **No email invitations**: Members are added directly by admins via API
- **No workspace templates**: Create empty, populate manually (or via import, future)
- **No anonymous read for private workspaces**: Private means members-only, period
- **No IP-based editing** (Phase 1): Only authenticated users, even for public workspaces
- **No real-time collaboration** (OT/CRDT): Same optimistic-concurrency model as existing (none), not adding it here

**Test Strategy:**

## Verification Strategy

### 1. Data Model Tests (`tests/platform/test_workspaces.py`)

**Workspace CRUD**:
```python
def test_create_workspace():
    """Public workspace with valid params creates successfully."""
    workspace = create_workspace(
        id="test-public",
        display_name="Test Public",
        visibility="public",
        edit_policy="admin_only",
        catalog_path="/tmp/test-catalog.json",
        corpus_root="/tmp/corpus",
        reviews_dir="/tmp/reviews",
        created_by="test-user"
    )
    assert workspace.id == "test-public"
    assert workspace.visibility == "public"

def test_reject_invalid_visibility():
    """Creating workspace with invalid visibility enum fails."""
    with pytest.raises(ValueError, match="visibility"):
        create_workspace(..., visibility="invalid", ...)

def test_duplicate_catalog_path_rejected():
    """Two workspaces cannot share the same catalog_path."""
    create_workspace(..., catalog_path="/tmp/catalog.json", ...)
    with pytest.raises(IntegrityError):
        create_workspace(..., catalog_path="/tmp/catalog.json", ...)
```

**Membership & Authorization**:
```python
def test_workspace_member_roles():
    """Admin/member/viewer roles have correct permissions."""
    workspace = create_workspace(..., visibility="private", edit_policy="admin_only")
    add_member(workspace.id, "alice", role="admin")
    add_member(workspace.id, "bob", role="member")
    
    assert can_read(workspace, user="alice") == True
    assert can_write(workspace, user="alice") == True
    assert can_admin(workspace, user="alice") == True
    
    assert can_read(workspace, user="bob") == True
    assert can_write(workspace, user="bob") == False  # Phase 1: admin_only editing
    assert can_admin(workspace, user="bob") == False

def test_public_workspace_anonymous_read():
    """Public workspace allows unauthenticated reads."""
    workspace = create_workspace(..., visibility="public")
    assert can_read(workspace, user=None) == True
    assert can_write(workspace, user=None) == False

def test_private_workspace_blocks_anonymous():
    """Private workspace blocks all unauthenticated access."""
    workspace = create_workspace(..., visibility="private")
    assert can_read(workspace, user=None) == False
    assert can_write(workspace, user=None) == False
```

### 2. Webapp Authorization Tests (`tests/webapp/test_workspace_auth.py`)

**Endpoint access control** (using FastAPI TestClient):
```python
def test_public_workspace_read_works_anonymous(client):
    """GET /api/{public_workspace}/pages works without auth."""
    response = client.get("/api/test-public/pages")
    assert response.status_code == 200

def test_private_workspace_read_requires_auth(client):
    """GET /api/{private_workspace}/pages returns 401 without auth."""
    response = client.get("/api/acme-private/pages")
    assert response.status_code == 401

def test_write_requires_admin_phase1(client, logged_in_member):
    """POST /api/{workspace}/citations returns 403 for non-admin (Phase 1)."""
    response = client.post(
        "/api/test-public/citations",
        json={...},
        cookies=logged_in_member  # member role, not admin
    )
    assert response.status_code == 403
    assert "admin-only" in response.json()["detail"].lower()

def test_admin_can_write(client, logged_in_admin):
    """POST /api/{workspace}/citations succeeds for admin."""
    response = client.post(
        "/api/test-public/citations",
        json={...},
        cookies=logged_in_admin
    )
    assert response.status_code == 201
```

**Workspace management**:
```python
def test_create_workspace_requires_auth(client):
    """POST /api/workspaces returns 401 without auth."""
    response = client.post("/api/workspaces", json={...})
    assert response.status_code == 401

def test_list_workspaces_shows_public_and_own_private(client, logged_in_user):
    """GET /api/workspaces returns public + user's private workspaces only."""
    create_workspace(id="public-1", visibility="public")
    create_workspace(id="public-2", visibility="public")
    create_workspace(id="private-alice", visibility="private", members=["alice"])
    create_workspace(id="private-bob", visibility="private", members=["bob"])
    
    response = client.get("/api/workspaces", cookies=logged_in_user("alice"))
    workspace_ids = [w["id"] for w in response.json()]
    assert set(workspace_ids) == {"public-1", "public-2", "private-alice"}
    assert "private-bob" not in workspace_ids
```

### 3. Workspace Isolation Tests (`tests/platform/test_workspace_isolation.py`)

**Data isolation** (end-to-end):
```python
def test_workspaces_use_separate_catalogs():
    """Two workspaces have independent catalogs, no cross-contamination."""
    workspace_a = create_workspace(catalog_path="/tmp/catalog-a.json", ...)
    workspace_b = create_workspace(catalog_path="/tmp/catalog-b.json", ...)
    
    # Add citation to workspace A
    add_citation(workspace_a, fact_key="test", ...)
    
    # Workspace B's catalog is untouched
    pages_b = list_pages(workspace_b.catalog_path)
    assert "test" not in pages_b
    
    # Workspace A's catalog has the citation
    pages_a = list_pages(workspace_a.catalog_path)
    assert "test" in pages_a

def test_review_decisions_scoped_per_workspace():
    """Review decisions in one workspace don't affect another."""
    workspace_a = create_workspace(reviews_dir="/tmp/reviews-a", ...)
    workspace_b = create_workspace(reviews_dir="/tmp/reviews-b", ...)
    
    # Record review in workspace A
    record_review(workspace_a.reviews_dir, fact_key="test", verdict="approved", ...)
    
    # Workspace B's review consultation doesn't see A's decision
    prior_decisions = consult_prior_reviews(workspace_b.reviews_dir, ...)
    assert len(prior_decisions) == 0
```

### 4. Bootstrap Migration Test (`tests/platform/test_bootstrap.py`)

**Existing data preservation**:
```python
def test_bootstrap_preserves_existing_catalog():
    """Bootstrap script creates workspace without modifying existing catalog file."""
    original_catalog = Path("/work/ontologies/mikadiv-fm/references.json").read_text()
    
    bootstrap_default_workspace()
    
    # Catalog file is byte-for-byte identical
    assert Path("/work/ontologies/mikadiv-fm/references.json").read_text() == original_catalog
    
    # Workspace points to it
    workspace = get_workspace("mikadiv-fm-public")
    assert workspace.catalog_path == "/work/ontologies/mikadiv-fm/references.json"

def test_bootstrap_idempotent():
    """Running bootstrap twice doesn't create duplicates."""
    bootstrap_default_workspace()
    bootstrap_default_workspace()  # should no-op or update
    
    workspaces = list_workspaces()
    assert sum(1 for w in workspaces if w.id == "mikadiv-fm-public") == 1
```

### 5. Frontend Tests (`webapp/frontend/src/tests/`)

**Workspace navigation** (React Testing Library + Vitest):
```typescript
test('workspace selector shows public workspaces when logged out', async () => {
  render(<WorkspaceSelector />);
  await waitFor(() => {
    expect(screen.getByText('mikadiv-fm-public')).toBeInTheDocument();
    expect(screen.queryByText('acme-private')).not.toBeInTheDocument();
  });
});

test('login required message shown for private workspace', async () => {
  const { getByText } = render(<WorkspaceDetail id="acme-private" />);
  expect(getByText(/login required/i)).toBeInTheDocument();
});

test('edit buttons disabled for non-admin users', async () => {
  // Mock logged-in member (not admin)
  mockCurrentUser({ id: 'bob', role: 'member' });
  
  render(<AddCitationView workspaceId="test-public" />);
  const submitButton = screen.getByRole('button', { name: /submit citation/i });
  expect(submitButton).toBeDisabled();
  expect(screen.getByText(/admin-only editing/i)).toBeInTheDocument();
});
```

### 6. End-to-End Scenario Tests (Manual Verification Checklist)

**Public workspace flow**:
- [ ] Anonymous user visits `/` and sees list of public workspaces
- [ ] Click "mikadiv-fm-public" → can browse pages, view candidates, see review summary
- [ ] Attempt to submit citation → redirected to login
- [ ] Login as admin → citation submission works
- [ ] Login as member → citation submission blocked with "admin-only" message

**Private workspace flow**:
- [ ] Anonymous user visits `/w/acme-private` → 401 or redirect to login
- [ ] Login as non-member → 403 "not a workspace member"
- [ ] Login as member → can read pages, candidates, reviews
- [ ] Login as member → cannot submit citations (Phase 1: admin-only)
- [ ] Login as admin → can submit citations, manage workspace settings

**Workspace isolation**:
- [ ] Create citation in workspace A with fact_key "test"
- [ ] Switch to workspace B → "test" page does not exist
- [ ] Run staleness sweep in workspace A → flags drift
- [ ] Review and approve drift in workspace A
- [ ] Run staleness sweep in workspace B with same corpus → still flags drift (separate review history)

**Bootstrap verification**:
- [ ] Run bootstrap script
- [ ] Existing `/work/ontologies/mikadiv-fm/references.json` unchanged (compare checksums)
- [ ] New workspace "mikadiv-fm-public" exists and points to that catalog
- [ ] Can browse existing pages through workspace-scoped routes (`/w/mikadiv-fm-public/pages`)

### 7. Security Tests (`tests/platform/test_security.py`)

**Session fixation / CSRF** (if applicable):
```python
def test_login_regenerates_session_id():
    """Login creates new session, doesn't reuse existing one."""
    # Implementation depends on session library chosen
    pass

def test_logout_invalidates_session():
    """Logout clears session cookie and server-side state."""
    pass
```

**Injection attacks**:
```python
def test_workspace_id_sql_injection_blocked():
    """Malicious workspace_id doesn't execute SQL."""
    response = client.get("/api/'; DROP TABLE workspaces; --/pages")
    assert response.status_code in (404, 400)  # not 500
    # Workspace table still exists
    assert workspace_table_exists()
```

### Success Criteria (All Must Pass)

1. ✅ All unit tests pass (`pytest tests/platform/`)
2. ✅ All webapp tests pass (`pytest tests/webapp/`)
3. ✅ All frontend tests pass (`npm test` in `webapp/frontend/`)
4. ✅ Bootstrap script runs successfully and existing catalog is unchanged
5. ✅ Manual end-to-end checklist completed for public/private/isolation scenarios
6. ✅ At least 2 workspaces exist (one public, one private) with different corpora
7. ✅ Documentation updated: README has multi-workspace setup instructions
8. ✅ API documentation generated (OpenAPI/Swagger at `/docs` reflects new routes)
