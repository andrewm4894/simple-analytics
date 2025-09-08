# Simple Analytics Stack - Design Document

## Overview
Building a lightweight analytics stack using Django (backend) and React (frontend) for collecting, processing, and visualizing flexible event data with near real-time processing.

## Architecture Decisions

### Core Stack
- **Backend**: Django + Django REST Framework
- **Database**: PostgreSQL (primary storage)
- **Cache/Stream**: Redis (ingestion buffer and caching)
- **Frontend**: React (future dashboard)
- **Tooling**: uv (Python package management) + Makefile

### Data Flow Architecture
```
Event Ingestion API → Redis Stream/Cache → Background Processor → PostgreSQL
       ↑ (Public Keys)                                               ↓
                                                            Dashboard API
                                                         ↑ (Private Keys)
```

### Event Data Schema
```json
{
  "event_id": "uuid",
  "project_id": "string", 
  "event_source": "string",
  "user_id": "string|null (with default)",
  "session_id": "string|null (with default: user_id + 60min window)",
  "event_name": "string",
  "event_properties": "jsonb",
  "timestamp": "datetime",
  "ip_address": "string",
  "user_agent": "string"
}
```

### Multi-Project Support
- **Dual API Key System**: Each project has separate keys for security isolation:
  - **Public API Keys** (`sa_*`): For event ingestion, safe for frontend use
  - **Private API Keys** (`sa_priv_*`): For dashboard data access, backend only
- Project-based data isolation and authentication
- Per-project configurable settings:
  - Rate limiting and quotas
  - Data retention policies (raw events, aggregated data)
  - Event source management (multiple sources per project)
  - CORS allowlist (or wildcard * option)
  - **Flexible sampling configuration** (project and source level)

### Security & Rate Limiting
- **Dual API key validation** per project with separate access scopes
- **PublicApiKeyAuthentication**: Event ingestion with public keys
- **PrivateApiKeyAuthentication**: Dashboard API access with private keys
- Rate limiting by project ID and IP address
- Input validation and sanitization
- SQL injection protection via ORM
- Project-based data isolation with custom permission classes

### Processing Pipeline
- **Near Real-time**: 1-5 minute processing delay acceptable
- **Redis Streams**: Reliable event queuing with consumer groups and automatic acknowledgment
- **Django-RQ Workers**: Background processing with burst mode and monitoring
- **Event Processing**: ~1 event/second with Redis → PostgreSQL pipeline
- **Aggregation Jobs**: Daily/hourly summaries with project-level analytics
- **Data Cleanup**: Configurable retention policies per project
- **Error Handling**: Fail-open approach for Redis failures, comprehensive logging
- **Monitoring**: Real-time status commands and processing statistics

## Development Environment Strategy

### Recommended: Hybrid Docker Approach
**Databases in Docker:**
- PostgreSQL container with persistent volumes
- Redis container for caching/streams
- Docker Compose for database orchestration

**Django Native Development:**
- uv for Python package management and virtual environments
- Native Django development server
- Direct database connections to containerized DBs

**Rationale:**
- ✅ Fast development iteration (no container rebuilds)
- ✅ Easy debugging and IDE integration
- ✅ Consistent database environments
- ✅ No manual database installation/configuration
- ✅ Works seamlessly with uv workflow
- ✅ Easy to dockerize Django later for deployment

### Alternative Approaches Considered:
**Full Docker:** Everything containerized
- Pros: Complete environment consistency
- Cons: Slower development, complex debugging, file sync issues

**No Docker:** Everything native
- Pros: Fastest development
- Cons: Manual DB setup, environment inconsistencies

### Development Tools
- uv for Python dependency management
- Makefile for common commands (start DBs, run tests, etc.)
- Local development focus initially
- **Code Quality**: Ruff, Black, isort, MyPy, Bandit with pre-commit hooks
- **Django Management Commands**: Custom commands for operational tasks and testing
- **Professional Error Handling**: Proper exception chaining and logging throughout

## Data Management
- **Raw Event Retention**: Configurable per project (default: 90 days)
- **Aggregated Data**: Configurable per project retention for summarized metrics
- **Indexing Strategy**: Composite indexes on (project_id, event_source, timestamp, event_name)
- **Partitioning**: PostgreSQL table partitioning by date for performance

## User Identification Strategy
- **Client-provided user_id**: Use if explicitly provided by client
- **Fallback generation**:
  - Browser: Cookie-based persistent identifier
  - API/Backend: Hash of (IP address + User-Agent + project salt)
- **Session ID**: `user_id + 60-minute time window` for grouping related events

## Flexible Sampling Strategy

### Sampling Levels
- **Project Level**: Default sampling settings applied to all events
- **Event Source Level**: Override project settings for specific sources
- **Event Level**: Runtime sampling decisions based on configured rules

### Sampling Strategies
```mermaid
graph TD
    Event[Incoming Event] --> Check{Sampling Enabled?}
    Check -->|No| Accept[Accept Event]
    Check -->|Yes| Strategy{Sampling Strategy}
    
    Strategy -->|Random| Random[random() < rate]
    Strategy -->|Deterministic| Hash[Hash user_id + project_id]
    Strategy -->|Time Window| Time[Time-based sampling]
    
    Random --> Decision{Accept?}
    Hash --> Decision
    Time --> Decision
    
    Decision -->|Yes| Accept
    Decision -->|No| Reject[Reject Event]
```

### Configuration Options
- **Random Sampling**: Pure random selection (10% = random 10% of events)
- **Deterministic Sampling**: Consistent sampling based on user_id hash (same users always sampled)
- **Time Window Sampling**: Sample within time periods (useful for consistent time-based analysis)

### Use Cases
- **Cost Control**: Sample 10% of events to reduce storage costs
- **Development**: Sample 1% of production traffic for testing
- **A/B Testing**: Deterministic sampling for consistent user experiences
- **High-Volume Sources**: Different sampling rates per event source

## Event Ingestion API Design

### Authentication & Rate Limiting
- **Public API Key Format**: `sa_<random_token>` for event ingestion
- **Private API Key Format**: `sa_priv_<random_token>` for dashboard access
- **Bearer token authentication** for both key types
- **Rate Limiting**: Redis-based sliding window (per project and per IP)
- **Fail-Open Design**: Continue processing if Redis rate limiting fails
- **Header Support**: Standardized `X-Forwarded-For` and `X-Real-IP` handling

### Request/Response Format
```json
// Request
POST /api/events/ingest/
Authorization: Bearer sa_<token>
Content-Type: application/json

{
  "event_name": "page_view",
  "event_source": "web_app",
  "user_id": "user_123",  // optional
  "session_id": "sess_abc",  // optional
  "event_id": "client_event_id",  // optional
  "properties": {
    "page": "/dashboard",
    "referrer": "https://google.com"
  },
  "timestamp": "2023-01-01T12:00:00Z"  // optional, defaults to server time
}

// Response (202 Accepted)
{
  "status": "accepted",
  "sampled": false
}
```

### Validation & Limits
- **Properties Size**: 64KB maximum when JSON-serialized
- **Event Name**: 255 characters maximum
- **Auto-Creation**: Event sources created automatically if not exists
- **Smart Defaults**: Timestamp, user_id, session_id auto-generated if missing

## Background Processing Architecture

### Event Processing Flow
```mermaid
graph TD
    A[Event Ingestion API] --> B[Redis Stream]
    B --> C[Consumer Group]
    C --> D[RQ Worker]
    D --> E[PostgreSQL Events]
    
    F[Scheduler] --> G[Aggregation Jobs]
    G --> H[Daily Summaries]
    G --> I[Hourly Aggregations]
    
    E --> G
    
    J[Cleanup Jobs] --> E
```

### Worker System Components
- **EventProcessor**: Core class handling Redis stream consumption
- **Consumer Groups**: Reliable message processing with automatic acknowledgment
- **RQ Jobs**: Scalable background task execution
- **Management Commands**: Operational tools for monitoring and control

### Aggregation Models
- **DailyEventAggregation**: Event counts by project/source/name per day
- **HourlyEventAggregation**: Event counts by project/source/name per hour
- **FiveMinuteEventAggregation**: Near real-time event counts for dashboard widgets
- **ProjectDailySummary**: Daily project statistics with top events and source breakdown

### Management Commands
- `process_events`: Process events from Redis stream (continuous or single-run)
- `aggregate_events`: Run daily/hourly aggregation jobs
- `cleanup_events`: Remove old events based on retention policies
- `event_status`: Monitor system health and processing statistics

### Performance Characteristics
- **Event Processing**: ~1 event/second per worker
- **Aggregation Speed**: 5 events aggregated in 0.09 seconds
- **Memory Efficient**: Batch processing with configurable batch sizes
- **Fault Tolerant**: Consumer groups prevent message loss
- **Scalable**: Multiple workers can process from same consumer group

## Monitoring & Observability
- **Health Checks**: Redis connection, PostgreSQL queries, worker status
- **Metrics**: Prometheus integration for ingestion rates, processing lag, error rates
- **Admin Dashboard**: Built-in monitoring section for system health and project stats
- **Alerting**: When processing falls behind or errors spike
- **Audit Logging**: API key usage, rate limit violations, system events

## Analytical Database Considerations

### Option 1: PostgreSQL Only (Start Here)
**Pros:**
- Single database to manage
- Excellent JSONB support for flexible querying
- Good performance with proper indexing
- Mature ecosystem and tooling

**Cons:** 
- Not optimized for heavy analytical workloads
- Row-based storage less efficient for aggregations

### Option 2: PostgreSQL + DuckDB Pipeline
**DuckDB Pros:**
- Columnar storage, excellent for analytics
- Fast aggregations and complex queries
- Can integrate with PostgreSQL via foreign data wrappers
- Embedded option reduces infrastructure complexity

**DuckDB Cons:**
- Additional complexity and data pipeline
- Another service to monitor and maintain
- Data synchronization overhead

**Recommendation**: Start with PostgreSQL + proper indexing. Consider DuckDB later if analytical query performance becomes a bottleneck.

## Dashboard API Design

### Authentication & Authorization
- **Private API Key Authentication**: `sa_priv_<token>` required for all dashboard endpoints
- **Project-based Data Isolation**: Users only see data for their authenticated project
- **Custom Permission Classes**: `IsProjectAuthenticated` for Project-based auth

### Dashboard API Endpoints

#### Event Querying
```
GET /api/events/query/
Authorization: Bearer sa_priv_<token>

Query Parameters:
- start_date: ISO datetime (default: 24h ago)
- end_date: ISO datetime (default: now)  
- event_name: Filter by event name
- event_source_id: Filter by event source
- user_id: Filter by user
- page: Page number
- page_size: Results per page (max 1000)
```

#### Aggregation Endpoints
```
GET /api/events/aggregations/daily/     # Daily aggregations
GET /api/events/aggregations/hourly/    # Hourly aggregations  
GET /api/events/aggregations/5min/      # 5-minute aggregations
GET /api/events/summaries/daily/        # Daily project summaries
```

#### Real-time Metrics
```
GET /api/events/metrics/realtime/       # Current stats for widgets
GET /api/events/names/                  # Unique event names
GET /api/events/sources/                # Event sources list
```

### Response Format & Performance
- **Pagination**: Standardized pagination with configurable page sizes
- **Time-based Filtering**: Efficient queries with proper date range defaults
- **Optimized Queries**: `select_related()` for performance
- **Project Isolation**: All queries automatically filtered by authenticated project

### Serializers & Data Structures
- **EventSerializer**: Raw event data with project/source relationships
- **AggregationSerializers**: Daily/hourly/5-minute aggregation data
- **RealTimeMetricsSerializer**: Dashboard widget data
- **TimeRangeFilterSerializer**: Flexible date range validation

## Future Dashboard Features (React Frontend)
- React application consuming Dashboard API
- Real-time dashboard widgets using 5-minute aggregations
- Interactive visualizations and charts
- Project management interface
- Data export capabilities
