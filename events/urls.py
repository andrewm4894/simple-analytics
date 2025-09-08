from django.urls import path

from . import views, views_dashboard

app_name = "events"

# Event Ingestion API
ingestion_patterns = [
    path("ingest/", views.EventIngestionView.as_view(), name="ingest"),
]

# Dashboard API - Event Querying
query_patterns = [
    path("query/", views_dashboard.EventQueryView.as_view(), name="query"),
    path("names/", views_dashboard.event_names_list, name="event_names"),
    path("sources/", views_dashboard.event_sources_list, name="event_sources"),
]

# Dashboard API - Aggregations
aggregation_patterns = [
    path(
        "aggregations/daily/",
        views_dashboard.DailyAggregationView.as_view(),
        name="daily_aggregations",
    ),
    path(
        "aggregations/hourly/",
        views_dashboard.HourlyAggregationView.as_view(),
        name="hourly_aggregations",
    ),
    path(
        "aggregations/5min/",
        views_dashboard.FiveMinuteAggregationView.as_view(),
        name="fivemin_aggregations",
    ),
    path(
        "summaries/daily/",
        views_dashboard.ProjectSummaryView.as_view(),
        name="daily_summaries",
    ),
]

# Dashboard API - Real-time Metrics
metrics_patterns = [
    path(
        "metrics/realtime/", views_dashboard.real_time_metrics, name="realtime_metrics"
    ),
]

urlpatterns = (
    ingestion_patterns + query_patterns + aggregation_patterns + metrics_patterns
)
