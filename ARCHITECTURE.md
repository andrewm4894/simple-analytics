# Simple Analytics Stack - Architecture Documentation

## System Overview

The Simple Analytics Stack is a flexible, multi-project analytics platform built with Django and designed for near real-time event processing and visualization.

## High-Level Architecture

```mermaid
graph TB
    Client[Client Applications] --> API[Django REST API]
    API --> Redis[Redis Cache/Streams]
    API --> PostgreSQL[(PostgreSQL Database)]
    Redis --> Workers[Background Workers]
    Workers --> PostgreSQL
    Dashboard[Analytics Dashboard] --> API
    Admin[Admin Panel] --> API
    
    subgraph "Data Flow"
        Client -->|Events| API
        API -->|Queue| Redis
        Redis -->|Process| Workers
        Workers -->|Store| PostgreSQL
        PostgreSQL -->|Query| Dashboard
    end
```

## Component Architecture

### 1. Data Ingestion Layer

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API Endpoint
    participant R as Redis Stream
    participant W as RQ Worker
    participant P as PostgreSQL

    C->>A: POST /api/events/ingest
    A->>A: Validate API Key
    A->>A: Rate Limit Check
    A->>A: CORS Validation
    A->>R: Queue Event
    A->>C: 202 Accepted
    
    R->>W: Process Event
    W->>W: Generate user_id if needed
    W->>W: Create session_id
    W->>P: Store Event
```

### 2. Multi-Project Architecture

```mermaid
erDiagram
    Project {
        uuid id PK
        string name
        string public_api_key
        string private_api_key
        json settings
        json cors_allowlist
        int rate_limit_per_minute
        int retention_days
        datetime created_at
        datetime updated_at
    }
    
    Event {
        uuid id PK
        uuid project_id FK
        string event_source
        string event_name
        string user_id
        string session_id
        jsonb event_properties
        string ip_address
        string user_agent
        datetime timestamp
        datetime created_at
    }
    
    EventSource {
        uuid id PK
        uuid project_id FK
        string name
        string description
        boolean is_active
        datetime created_at
    }
    
    Project ||--o{ Event : contains
    Project ||--o{ EventSource : manages
```

### 4. Background Processing Architecture

```mermaid
graph TD
    A[Event Ingestion API] --> B[Redis Stream: events]
    B --> C[Consumer Group: processors]
    C --> D[RQ Worker: EventProcessor]
    D --> E[PostgreSQL Events Table]
    
    F[Scheduler/Cron] --> G[Aggregation Jobs]
    G --> H[DailyEventAggregation]
    G --> I[HourlyEventAggregation]
    G --> I2[FiveMinuteEventAggregation]
    G --> J[ProjectDailySummary]
    
    E --> G
    
    K[Management Commands] --> L[process_events]
    K --> M[aggregate_events]
    K --> N[cleanup_events]
    K --> O[event_status]
```

**Key Components:**
- **Redis Streams**: Reliable message queuing with consumer groups
- **EventProcessor**: Core processing class handling event deserialization
- **RQ Jobs**: Scalable background task execution
- **Aggregation Models**: Pre-computed analytics for dashboard performance
- **Management Commands**: Operational tools for monitoring and control

### 5. Dashboard API Architecture

```mermaid
graph TD
    Client[Dashboard Client] --> Auth[Private API Key Auth]
    Auth --> Perm[IsProjectAuthenticated Permission]
    Perm --> API[Dashboard API Views]
    
    API --> EventQuery[Event Query View]
    API --> DailyAgg[Daily Aggregation View] 
    API --> HourlyAgg[Hourly Aggregation View]
    API --> FiveMinAgg[5-Min Aggregation View]
    API --> Summary[Project Summary View]
    API --> Metrics[Real-time Metrics]
    API --> Meta[Event Names/Sources]
    
    EventQuery --> PostgreSQL[(PostgreSQL)]
    DailyAgg --> PostgreSQL
    HourlyAgg --> PostgreSQL
    FiveMinAgg --> PostgreSQL
    Summary --> PostgreSQL
    Metrics --> PostgreSQL
    Meta --> PostgreSQL
    
    PostgreSQL --> Response[JSON Response]
    Response --> Pagination[Paginated Results]
```

**Key Components:**
- **PrivateApiKeyAuthentication**: Validates `sa_priv_*` tokens for dashboard access
- **IsProjectAuthenticated**: Custom permission ensuring Project-based data access
- **Specialized Views**: Dedicated endpoints for different data aggregation levels
- **Optimized Queries**: `select_related()` and proper filtering for performance
- **Pagination**: Configurable pagination with maximum page size limits

### 6. Development Environment Architecture

```mermaid
graph LR
    subgraph "Development Environment"
        Dev[Developer] --> uv[uv Virtual Environment]
        uv --> Django[Django Dev Server]
        Django --> DockerPG[(PostgreSQL Container)]
        Django --> DockerRedis[(Redis Container)]
        
        subgraph "Docker Compose"
            DockerPG
            DockerRedis
        end
        
        subgraph "Native Python"
            uv
            Django
            Worker[RQ Worker]
        end
        
        Django --> Worker
        Worker --> DockerRedis
        Worker --> DockerPG
    end
```

## Technology Stack

### Core Framework
- **Backend**: Django 5.2 + Django REST Framework
- **Database**: PostgreSQL 16 (containerized)
- **Cache/Queue**: Redis 7 (containerized)
- **Background Tasks**: Django-RQ

### Development Tools
- **Package Management**: uv (Python 3.11)
- **Task Runner**: Makefile
- **Containerization**: Docker Compose (databases only)
- **Environment**: python-dotenv

### Key Dependencies
```
django==5.2.6
djangorestframework==3.16.1
psycopg2-binary==2.9.10
redis==6.4.0
django-rq==3.1
django-cors-headers==4.7.0
django-extensions==4.1
python-dotenv==1.1.1
```

## Data Flow Patterns

### 1. Event Ingestion Flow
1. **Client** sends event via HTTP POST to `/api/events/ingest`
2. **API Endpoint** validates API key, checks rate limits, validates CORS
3. **Event** is queued in Redis stream for processing
4. **Background Worker** processes event from queue
5. **Worker** generates missing user_id/session_id if needed
6. **Event** is stored in PostgreSQL with full metadata

### 2. Dashboard API Flow
1. **Dashboard** requests data via REST API with private API key
2. **PrivateApiKeyAuthentication** validates private API key and project access
3. **IsProjectAuthenticated** permission ensures project-based data isolation
4. **PostgreSQL** queries with appropriate filters, aggregations, and pagination
5. **Results** returned as JSON with project-filtered data

### 3. Background Processing
1. **Redis Streams** hold incoming events in consumer groups
2. **Django-RQ Workers** consume events with reliable acknowledgment
3. **EventProcessor** handles:
   - Event deserialization from Redis
   - User ID generation (cookie-based or IP+UserAgent hash)
   - Session ID creation (user + 60min window)
   - Data validation and enrichment
   - Database storage with error handling
4. **Aggregation Jobs** create:
   - Daily event summaries by project/source/name
   - Hourly event statistics
   - 5-minute aggregations for real-time analytics
   - Project daily summaries with source breakdown

## Security Architecture

### Authentication & Authorization
- **Dual API Key System**: Separate security scopes for different operations
  - **Public API Keys** (`sa_*`): Event ingestion authentication (safe for frontend)
  - **Private API Keys** (`sa_priv_*`): Dashboard data access authentication (backend only)
- **Authentication Classes**:
  - **PublicApiKeyAuthentication**: Validates public keys for event ingestion
  - **PrivateApiKeyAuthentication**: Validates private keys for dashboard access
- **Custom Permissions**: `IsProjectAuthenticated` for project-based data access
- **CORS**: Configurable per-project allowlist
- **Rate Limiting**: Per-project and per-IP limits

### Data Isolation
- **Multi-tenant**: All queries automatically filtered by authenticated project
- **Project Settings**: Isolated configuration per project
- **Dual API Key Scoping**: Both public and private keys tied to specific projects
- **Authentication-based Filtering**: Dashboard API enforces project isolation through authentication

## Configuration Management

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/simple_analytics

# Redis  
REDIS_URL=redis://localhost:6379/0

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

### Project-Level Settings
Each project can configure:
- Rate limits and quotas
- Data retention policies  
- CORS allowlist
- Event source management

## Monitoring & Observability

### Current Implementation
- **Management Commands**: System monitoring via `event_status` command
- **Health Checks**: Database connectivity, Redis status, processing statistics
- **Worker Status**: RQ job monitoring and queue management
- **Error Handling**: Comprehensive exception logging throughout pipeline

### Planned Components  
- **Metrics**: Prometheus integration for ingestion rates and processing lag
- **Admin Dashboard**: Built-in system monitoring interface
- **Alerting**: When processing falls behind or errors spike

## Scalability Considerations

### Current Architecture
- **Single Django Instance**: Suitable for development and small-medium loads
- **Containerized Databases**: Easy to scale horizontally later
- **Queue-based Processing**: Natural scaling point for workers

### Future Scaling Options
- **Multiple Django Instances**: Load balanced API servers
- **Worker Scaling**: Multiple RQ worker processes/containers
- **Database Sharding**: Partition by project_id if needed
- **Read Replicas**: Separate read/write database instances

## Implementation Status

### ✅ Completed (Phases 1-4)
**Foundation (Phase 1):**
- uv project structure with professional development environment
- Docker Compose setup for PostgreSQL and Redis
- Django project with apps (projects, events)
- Makefile for common tasks and code quality tools

**Data Models (Phase 2):**
- Multi-project architecture with Project and EventSource models
- Flexible Event model with JSONB properties
- Sampling configuration at project and source levels
- User identification and session management

**Event Ingestion API (Phase 3):**
- High-performance `/api/events/ingest` endpoint
- API key authentication with Bearer token support
- Redis-based rate limiting (per project and IP)
- Comprehensive input validation and CORS handling
- Redis stream queuing for reliable event processing

**Background Processing (Phase 4):**
- Django-RQ worker system with EventProcessor class
- Redis stream consumption with consumer groups
- Event aggregation models (daily/hourly/5-minute summaries)
- Management commands for operational tasks
- Error handling and monitoring capabilities

**Dashboard API (Phase 5):**
- Complete Dashboard API with dual authentication system
- Event querying endpoints with filtering and pagination
- Aggregation endpoints (daily/hourly/5-minute analytics)
- Real-time metrics endpoints for dashboard widgets
- Project-based data isolation with custom authentication classes
- Performance-optimized queries with proper indexing

### 🚧 Current Focus (Phase 6)
- Comprehensive testing suite with unit and integration tests
- Load testing validation for high event volumes
- API documentation and developer tooling
- Performance monitoring and observability setup

### 📋 Planned (Phase 7+)
- React frontend dashboard consuming Dashboard API
- Interactive visualizations and charts
- Advanced monitoring and alerting
- Production deployment and scaling