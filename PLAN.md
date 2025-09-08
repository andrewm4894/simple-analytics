# Simple Analytics Stack - Implementation Plan

## Phase 1: Project Foundation
- [ ] Set up uv project structure and dependencies
- [ ] Create Makefile for common commands
- [ ] Docker Compose setup (Django, PostgreSQL, Redis)
- [ ] Django project initialization with DRF
- [ ] Basic project configuration and settings

## Phase 2: Core Data Models
- [ ] Project model (API keys, settings)
- [ ] Event model (flexible schema with JSONB)
- [ ] Database migrations and indexing strategy
- [ ] Session ID generation logic (user + 60min window)
- [ ] Data retention and cleanup policies

## Phase 3: Ingestion API
- [ ] Event ingestion REST endpoint
- [ ] API key authentication middleware
- [ ] Rate limiting per project and IP
- [ ] **Flexible sampling implementation** (project/source/event level)
- [ ] Input validation and sanitization
- [ ] Redis stream integration for event queuing

## Phase 4: Background Processing
- [ ] Choose worker system (Django-RQ vs Celery)
- [ ] Redis → PostgreSQL event processor
- [ ] Error handling and retry logic
- [ ] Monitoring and logging for processors
- [ ] Basic aggregation jobs

## Phase 5: Dashboard API
- [ ] Event querying API with filtering
- [ ] Project-based data isolation
- [ ] User authentication for dashboard
- [ ] Basic aggregation endpoints
- [ ] Performance optimization for queries

## Phase 6: Testing & Tooling
- [ ] Unit tests for models and APIs
- [ ] **Sampling strategy testing** (random, deterministic, time-window)
- [ ] Integration tests for ingestion pipeline
- [ ] Load testing scripts and scenarios (with sampling scenarios)
- [ ] Demo event generation scripts
- [ ] Performance monitoring setup

## Phase 7: Future Dashboard (Later)
- [ ] React application setup
- [ ] Dashboard UI components
- [ ] Real-time updates integration
- [ ] Visualization components
- [ ] Export functionality

## Current Focus: Backend First
Starting with Phases 1-6, using scripts and API testing tools for validation before building the frontend dashboard.

## Success Criteria Phase 1-6
- High-throughput event ingestion
- Reliable Redis → PostgreSQL pipeline
- Multi-project isolation and security
- Load testing validation
- Comprehensive API documentation