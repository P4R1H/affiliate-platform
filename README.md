# Rough notes
poetry over pip

That makes sense, lets get rid of the image proof to save up on the bandwidth & storage while keeping view count as fallback
The verification is enough of a deterrant to not fake views & someone who really wants to fake views would not have a tough time faking the screenshot as well

affiliates can provide api key through which we can access information from their posts which we couldnt otherwise

Moved to queue based reconcilation over cronjob based

Stopped collecting proof images

---

# Affiliate Reconciliation Platform

End-to-end system for receiving affiliate-reported performance metrics, normalizing and verifying them against platform-sourced data, and surfacing discrepancies & trust signals—optimized for extensibility and rapid iteration.

## Table of Contents
- [System Overview](#system-overview)
- [Why Mock Platforms](#why-mock-platforms)
- [Why We Removed Image Proofs](#why-we-removed-image-proofs)
- [Architecture](#architecture)
- [Data Model & Integrity](#data-model--integrity)
- [Reconciliation Lifecycle](#reconciliation-lifecycle)
- [Enhancements vs Brief](#enhancements-vs-brief)
- [Assumptions & Design Choices](#assumptions--design-choices)
- [RBAC & Security](#rbac--security)
- [API Surface (Implemented)](#api-surface-implemented)
- [Running Locally](#running-locally)
- [Extending the System](#extending-the-system)
- [Future Opportunities](#future-opportunities)

## System Overview

Core responsibilities:
1. Accept affiliate submissions (API now; Discord-style ingestion planned but schema-ready).
2. Normalize links & enrich platform context (e.g., Reddit permalink normalization).
3. Generate or fetch platform truth metrics (mock adapters for now; real integration boundary preserved).
4. Reconcile claims vs truth & log discrepancies for auditability.
5. Maintain affiliate trust score as lightweight fraud/quality signal.
6. Expose structured, typed API responses for downstream dashboards / analytics.

Status: A lean but production-aligned core—no speculative abstractions, only primitives required by the brief + targeted integrity & governance improvements.

## Why Mock Platforms
The brief explicitly permits mocking platform APIs. We deliberately mock Reddit/Instagram/TikTok/YouTube/X for the following reasons:
- Cost & Rate Limits: Real APIs often require credentials, rate negotiation, or long review cycles.
- Deterministic Testing: Mocks let us exercise edge paths (timeouts, partial data, random latency) without flakiness.
- Extensibility Contract: Each adapter already conforms to a unified `PlatformAPIResponse` → `UnifiedMetrics` conversion. Swapping in a real client is a drop-in replacement (just implement fetch + transform).
- Risk Isolation: Avoids external dependency drift during reconciliation correctness evolution.

We still perform a real-ish network normalization pass for Reddit URLs to prove boundary design (link canonicalization), while metrics remain simulated.

## Why We Removed Image Proofs
Originally submissions contemplated screenshot/image evidence. We eliminated image uploads because:
- Reconciliation Supersedes Static Proofs: Platform-fetched metrics are authoritative; screenshots become redundant & manipulable.
- Bandwidth & Storage Overhead: Eliminated binary storage, simplifying infra & security posture.
- Attack Surface Reduction: Less surface for exfiltration / malware payloads via image metadata.
- Developer Velocity: Faster iteration focusing on reconciliation core instead of object storage orchestration.

Fallback Strategy: If a platform API later restricts a metric, we can re-introduce selective lightweight evidence fields (already supported via `evidence_data` JSON) without reworking persistence.

## Architecture

```
Clients (Affiliates) ─┐
              ▼
          FastAPI HTTP Layer
              ▼
    ┌──────── Domain / Services ────────┐
    │  Submissions  |  Integrations     │
    │  Reconciliation (sync placeholder)│
    └────────────────┬──────────────────┘
             ▼
         Persistence (SQLAlchemy)
             ▼
         Structured Logging Layer
```

Modular integration adapters expose consistent metric structures; reconciliation logic consumes affiliate + platform reports to produce logs & trust score updates.

## Data Model & Integrity

Highlights:
- Post-centric granularity (one row per unique affiliate-platform-campaign URL) with uniqueness constraint.
- Append-only affiliate report history; platform fetch snapshots stored separately.
- Reconciliation logs capture comparison outcome (scaffold present; thresholds enforced in services layer).
- Enforced uniqueness: affiliate email + name + per-post uniqueness composite constraint.
- Enums introduced (`CampaignStatus`, `UserRole`) to remove fragile string literals.
- Role column added to `Affiliate` enabling RBAC without introducing a parallel user table.

## Reconciliation Lifecycle
Current: Triggered on submission (synchronous placeholder) or via explicit endpoint.
Roadmap (deferred): Offload to queue / worker for isolation & retry semantics.
Stages:
1. Affiliate submits claim.
2. Link normalization + platform adapter call (mock returns metrics / or defers to upstream).
3. Metrics persisted as affiliate report + (optional) platform report.
4. Discrepancy computation logged (future: alert thresholds drive `Alert` creation).
5. Trust score recalculated (simple accuracy ratio now; extensible for weighted rules).

## Enhancements vs Brief
| Brief Item | Delivered | Enhancement Notes |
|------------|-----------|------------------|
| Multi-platform integrations | Yes (mock adapters) | Uniform response contract; easy real API swap |
| Two reporting modes | API implemented; Discord-ready schema | `submission_method` Enum persisted |
| Reconciliation frequency | On-demand + per-submission model | Faster feedback vs batch cron |
| Detect inconsistencies | Uniqueness + discrepancy scaffolding + alerts model | Threshold logic extendable |
| Unified view | `UnifiedMetrics` + normalized platform schemas | Minimizes downstream branching |
| Logging / observability | Structured logger + performance events | Business & timing metadata keyed by request |
| Modularity/extensibility | Adapter isolation + enums + schemas | Low coupling between layers |
| RBAC | Minimal role-based admin guard | Extensible dependency pattern |
| Trust scoring | Implemented baseline | Supports future weighting |

## Assumptions & Design Choices
- **Mock-first** to accelerate iteration; external real clients mountable behind existing adapter signatures.
- **Enum Hardening** reduced typo risk + simplified validation logic.
- **No Image Storage** (see rationale above) to streamline MVP and reduce operational burden.
- **Immediate Reconciliation** over scheduled batch for increased affiliate feedback precision.
- **Localized Constants** for mock integrations to avoid premature global config bloat.
- **Pydantic V2 Migration (Partial)** replaced deprecated `.dict()` / `.from_orm()` usage in core endpoints; remaining schemas can be migrated incrementally.

## RBAC & Security
- Authentication: Bearer API key issued at affiliate creation.
- Role-based admin enforcement implemented for campaign creation (ADMIN only).
- Future: granular scopes (platform management, reconciliation control) if needed.

## API Surface (Implemented)
Core (current working subset):
```
POST   /api/v1/affiliates/               # Create affiliate (returns api_key)
GET    /api/v1/affiliates/me             # Authenticated affiliate profile
PUT    /api/v1/affiliates/me             # Update own profile

POST   /api/v1/campaigns/                # (ADMIN) Create campaign
GET    /api/v1/campaigns/                # List campaigns (enum filter)

POST   /api/v1/submissions/              # Submit post & claimed metrics
PUT    /api/v1/submissions/{post_id}/metrics  # Update claimed metrics
GET    /api/v1/submissions/history       # List own posts
GET    /api/v1/submissions/{post_id}/metrics # Metrics evolution

POST   /api/v1/reconciliation/run        # Trigger reconciliation (scaffold)
GET    /api/v1/reconciliation/results    # List reconciliation logs

GET    /api/v1/alerts/                   # List alerts (none if no discrepancies yet)
```

## Running Locally

### Prerequisites
- Python 3.11+
- (Optional) PostgreSQL / For tests we use in-memory SQLite

### Install (Poetry)
```
poetry install
poetry run pytest -q
poetry run uvicorn app.main:app --reload
```

### Minimal Env
Copy `.env.example` → `.env` and adjust if adding real DB / external APIs.

## Extending the System
Add a new platform:
1. Create `app/integrations/<platform>.py` implementing fetch + unify.
2. Add platform row via seed or factory.
3. Wire into submission normalization if URL patterns differ.

Add real API integration:
1. Replace mock metric generation with HTTP client logic.
2. Return data mapped to `PlatformAPIResponse`.
3. Preserve schema fields to avoid downstream changes.

Add richer reconciliation logic:
1. Implement threshold matrix in `services/reconciliation.py`.
2. Emit `Alert` rows when breach occurs.
3. Enhance trust score weighting.

## Future Opportunities
- Background worker (Celery / RQ) for async reconciliation & retries.
- Rate limiting + circuit breaking around real platform clients.
- Structured OpenTelemetry traces (current logger already provides request & operation context).
- Idempotency keys (currently duplicate prevention handled by composite uniqueness + logic).
- Bulk campaign/affiliate admin endpoints (guarded by roles).
- Metrics API for aggregated dashboards (currently derivable through queries).

---
Historical design notes retained above the delimiter for context & decision traceability.

## Architecture

### Core Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Affiliates    │    │   Advertisers   │    │   Platforms     │
│   (Submit)      │    │   (Dashboard)   │    │   (Verify)      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway                                  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ Posts   │ │Platform │ │Reconcil │
    │Service  │ │Service  │ │Service  │
    └─────────┘ └─────────┘ └─────────┘
          │           │           │
          └───────────┼───────────┘
                      ▼
            ┌─────────────────┐
            │   Job Queue     │
            │ (Reconciliation)│
            └─────────────────┘
                      │
                      ▼
            ┌─────────────────┐
            │   Database      │
            │ (PostgreSQL)    │
            └─────────────────┘
```

### Technology Stack
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Validation**: Pydantic schemas
- **Job Queue**: (To be implemented - Redis + Celery)
- **Platform Integrations**: Modular adapter pattern

## Database Design

### Post-Centric Architecture
Our key architectural decision was adopting a **post-centric model** rather than campaign-level aggregation:

```sql
Campaign (1) ──── (N) Post (1) ──── (N) AffiliateReport
                     │                        │
                     │                        │
                     └── (N) PlatformReport   │
                                              │
                                              ▼
                                    ReconciliationLog
```

### Core Tables

#### 1. **posts** - Individual Content Tracking
```sql
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    affiliate_id INTEGER REFERENCES affiliates(id), 
    platform_id INTEGER REFERENCES platforms(id),
    url VARCHAR NOT NULL,
    title VARCHAR,
    description TEXT,
    is_reconciled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(campaign_id, platform_id, url, affiliate_id)
);
```

#### 2. **affiliate_reports** - Affiliate Claims (Append-Only)
```sql
CREATE TABLE affiliate_reports (
    id SERIAL PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id),
    claimed_views INTEGER DEFAULT 0,
    claimed_clicks INTEGER DEFAULT 0,
    claimed_conversions INTEGER DEFAULT 0,
    evidence_data JSONB,
    submission_method VARCHAR, -- 'API' or 'DISCORD'
    status VARCHAR DEFAULT 'PENDING',
    submitted_at TIMESTAMP DEFAULT NOW()
);
```

#### 3. **platform_reports** - Platform Truth Data
```sql
CREATE TABLE platform_reports (
    id SERIAL PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id),
    platform_id INTEGER REFERENCES platforms(id),
    views INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0, 
    conversions INTEGER DEFAULT 0,
    spend DECIMAL(10,2) DEFAULT 0.00,
    raw_data JSONB,
    fetched_at TIMESTAMP DEFAULT NOW()
);
```

#### 4. **reconciliation_logs** - Comparison Results
```sql
CREATE TABLE reconciliation_logs (
    id SERIAL PRIMARY KEY,
    affiliate_report_id INTEGER REFERENCES affiliate_reports(id),
    platform_report_id INTEGER REFERENCES platform_reports(id),
    status VARCHAR, -- 'MATCHED', 'DISCREPANCY', etc.
    discrepancy_level VARCHAR, -- 'LOW', 'MEDIUM', 'HIGH'
    views_discrepancy INTEGER,
    clicks_discrepancy INTEGER,
    conversions_discrepancy INTEGER,
    views_diff_pct DECIMAL(5,2),
    clicks_diff_pct DECIMAL(5,2),
    conversions_diff_pct DECIMAL(5,2),
    processed_at TIMESTAMP DEFAULT NOW()
);
```

#### 5. **affiliates** - Partner Management with Trust Scoring
```sql
CREATE TABLE affiliates (
    id SERIAL PRIMARY KEY,
    name VARCHAR UNIQUE,
    email VARCHAR UNIQUE,
    discord_user_id VARCHAR,
    api_key VARCHAR UNIQUE,
    trust_score DECIMAL(3,2) DEFAULT 1.00,
    total_submissions INTEGER DEFAULT 0,
    accurate_submissions INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Data Integrity Constraints
- **Duplicate Prevention**: Unique constraint on `(campaign_id, platform_id, url, affiliate_id)` prevents same affiliate from submitting identical posts
- **Referential Integrity**: All foreign keys with proper cascade rules
- **Data Validation**: Check constraints for non-negative metrics and trust scores between 0-1

## Data Flow

### 1. Affiliate Submission Flow
```
POST /affiliates/submissions
    │
    ▼
┌─────────────────┐
│ Validate Schema │ ← AffiliatePostSubmission
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Create Post     │ ← posts table
└─────────────────┘
    │
    ▼
┌─────────────────┐
│Create AffReport │ ← affiliate_reports table
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Queue Recon Job │ ← reconciliation_job(affiliate_report_id)
└─────────────────┘
```

### 2. Reconciliation Job Flow
```
reconciliation_worker(affiliate_report_id)
    │
    ▼
┌─────────────────┐
│ Fetch Platform  │ ← Platform Integration Service
│ Data for Post   │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│Create PlatReport│ ← platform_reports table  
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Compare Metrics │ ← Business Logic
└─────────────────┘
    │
    ▼
┌─────────────────┐
│Create ReconLog  │ ← reconciliation_logs table
└─────────────────┘
    │
    ▼
┌─────────────────┐
│Update Trust     │ ← Update affiliate.trust_score
│Score            │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│Generate Alerts  │ ← If discrepancy > threshold
│(if needed)      │
└─────────────────┘
```

### 3. Unified Dashboard Flow
```
GET /dashboard/campaigns/{id}
    │
    ▼
┌─────────────────┐
│ Aggregate Data  │ ← Join posts, affiliate_reports, 
│ Across Posts    │   platform_reports, reconciliation_logs
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Transform to    │ ← CampaignDashboard schema
│ Unified Schema  │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Return JSON     │ ← Standardized response format
└─────────────────┘
```

## Key Improvements Over Requirements

### 1. **Real-Time Processing vs Batch Reconciliation**
- **Original**: "At a configurable frequency, reconcile affiliate-reported data"
- **Our Approach**: Job queue triggers reconciliation immediately upon affiliate submission
- **Benefits**: 
  - Faster feedback to affiliates
  - Better resource utilization
  - Simpler matching logic (1:1 post reconciliation)
  - Easier error handling and retry logic

### 2. **Post-Centric Data Model**
- **Original**: Implied campaign or date-level aggregation
- **Our Approach**: Individual post tracking with snapshot history
- **Benefits**:
  - Better duplicate detection
  - Granular audit trails
  - Support for tracking metric growth over time
  - More precise reconciliation matching

### 3. **Trust Scoring System**
- **Enhancement**: Built-in affiliate reliability tracking
- **Implementation**: Simple accuracy percentage with room for complexity
- **Benefits**: Dispute resolution, fraud detection, partner management

### 4. **Unified Metrics Schema**
- **Enhancement**: Platform-agnostic internal data representation
- **Implementation**: `UnifiedMetrics` Pydantic schema
- **Benefits**: Easy integration of new platforms, consistent API responses

## Assumptions & Decisions

### Platform Integrations
- **Mock vs Real APIs**: Designed for easy switching between mock and real platform APIs
- **Rate Limiting**: Will implement backoff strategies in integration layer
- **API Costs**: Assuming reasonable API quotas; will implement caching if needed

### Reconciliation Logic
- **A ≤ B Normal**: Affiliate claims less than platform data is expected (metrics grow over time)
- **A >> B Suspicious**: Affiliate overclaiming flagged for review
- **Thresholds**: 
  - Low discrepancy: < 5% difference
  - Medium discrepancy: 5-20% difference  
  - High discrepancy: > 20% difference

### Data Storage Decisions
- **Evidence Storage**: JSON fields for flexibility, no separate file storage for MVP
- **Secrets Management**: Simple JSON storage for API configs (sufficient for demo)
- **Audit Requirements**: Append-only affiliate_reports, immutable reconciliation logs

### Discord Integration
- **No Screenshots**: Removed image storage to reduce complexity and bandwidth
- **Structured Input**: Expecting parsed Discord data, not raw message processing
- **Idempotency**: Will handle via submission method and evidence data matching

### Trust Scoring
- **Simple Algorithm**: `accurate_submissions / total_submissions`
- **Update Frequency**: Recalculated after each reconciliation
- **Storage**: Materialized for performance, recalculated as needed

## API Endpoints

### Campaign Management
```
POST   /campaigns                    # Create campaign with platform assignments
GET    /campaigns                    # List all campaigns  
GET    /campaigns/{id}               # Get campaign details
PUT    /campaigns/{id}/platforms     # Update platform assignments
```

### Affiliate Operations
```
POST   /affiliates/submissions      # Submit post with claimed metrics
GET    /affiliates/{id}/submissions # View submission history
GET    /affiliates/{id}/performance # Trust score and statistics
```

### Platform Integration
```
POST   /platforms/{platform}/fetch  # Manual platform data fetch
GET    /platforms/{platform}/status # Integration health check
PUT    /platforms/{platform}/config # Update API configuration
```

### Reconciliation & Monitoring
```
POST   /reconciliation/run          # Manual reconciliation trigger
GET    /reconciliation/runs/{id}    # Detailed reconciliation results
GET    /alerts                      # Active alerts and discrepancies
PUT    /alerts/{id}/resolve         # Resolve alert with notes
```

### Dashboard & Reporting
```
GET    /dashboard/campaigns/{id}    # Unified campaign metrics
GET    /dashboard/affiliates       # Affiliate performance overview
GET    /dashboard/discrepancies    # Problem areas requiring attention
```

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- Redis (for job queue)

### Installation
```bash
# Clone repository
git clone <repository-url>
cd affiliate-reconciliation-platform

# Install dependencies
pip install -r requirements.txt

# Set up database
createdb affiliate_reconciliation
alembic upgrade head

# Start Redis for job queue
redis-server

# Run application
uvicorn app.main:app --reload
```

### Environment Variables
```bash
DATABASE_URL=postgresql://user:pass@localhost/affiliate_reconciliation
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key

# Platform API Keys (will be moved to database config)
REDDIT_CLIENT_ID=your-reddit-client-id
INSTAGRAM_ACCESS_TOKEN=your-instagram-token
META_ACCESS_TOKEN=your-meta-token
```

## Typing & ORM Conventions

The codebase uses SQLAlchemy 2.0 style typed ORM and Pydantic v2:

* `Mapped[...]` + `mapped_column()` for all model columns.
* `from __future__ import annotations` in each model to defer evaluation of forward references.
* Forward references imported only under `if TYPE_CHECKING:` to satisfy static analysis without runtime circular imports.
* Enum columns compared by coercing to string: `current = getattr(model.status, "value", model.status)`.
* API responses leverage `ResponseBase` which now allows an optional `data: Dict[str, Any]` payload.

When adding models:
1. Use precise Python types (e.g. `int`, `float`, `dict | None`).
2. Prefer explicit `list[Related]` over `Sequence` for relationship collections.
3. Keep business logic out of models—place it in service layers.
4. Update Pydantic schemas with `from_attributes = True` for ORM serialization.


### Sample Data Setup
```bash
# Create sample campaigns, platforms, and affiliates
python scripts/seed_data.py

# Submit test affiliate posts
python scripts/create_test_submissions.py

# Trigger reconciliation
python scripts/run_reconciliation.py
```

## Development Phases

- [x] **Phase 1**: Database design and core models
- [x] **Phase 2**: Pydantic schemas and validation
- [x] **Phase 3**: API endpoints and routing
- [x] **Phase 4**: Platform integration services
- [ ] **Phase 5**: Reconciliation job queue
- [ ] **Phase 6**: Dashboard and unified views
- [ ] **Phase 7**: Alerting and monitoring

## Next Steps
1. Implement FastAPI endpoints using the defined schemas
2. Create platform integration services with adapter pattern
3. Set up job queue system for reconciliation processing
4. Build dashboard views with aggregated metrics
5. Add comprehensive logging and monitoring