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
        string api_key
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

### 3. Development Environment Architecture

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

### 2. Query Flow
1. **Dashboard** requests data via REST API
2. **API** validates user authentication and project access
3. **PostgreSQL** queries with appropriate filters and aggregations
4. **Results** returned as JSON with pagination

### 3. Background Processing
1. **Redis Streams** hold incoming events
2. **RQ Workers** consume events from streams
3. **Workers** handle:
   - User ID generation (cookie-based or IP+UserAgent hash)
   - Session ID creation (user + 60min window)
   - Data validation and enrichment
   - Database storage

## Security Architecture

### Authentication & Authorization
- **API Keys**: Project-based authentication for event ingestion
- **Session Auth**: Django sessions for dashboard access
- **CORS**: Configurable per-project allowlist
- **Rate Limiting**: Per-project and per-IP limits

### Data Isolation
- **Multi-tenant**: All queries filtered by project_id
- **Project Settings**: Isolated configuration per project
- **API Key Scoping**: Keys tied to specific projects

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

### Planned Components
- **Health Checks**: Database connectivity, Redis status, worker health
- **Metrics**: Prometheus integration for ingestion rates and processing lag
- **Logging**: Structured logging with configurable levels
- **Admin Dashboard**: Built-in system monitoring

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

### ✅ Completed (Phase 1)
- uv project structure with dependencies
- Docker Compose setup for databases
- Django project with apps (projects, events)
- Basic configuration and settings
- Makefile for common tasks

### 🚧 In Progress
- Core data models (Project, Event)
- API authentication middleware
- Event ingestion endpoints

### 📋 Planned
- Background processing with RQ
- Dashboard API endpoints
- Admin interface
- Monitoring and health checks
- Load testing and performance optimization