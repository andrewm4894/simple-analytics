export interface Event {
  id: number;
  event_name: string;
  user_id: string;
  session_id: string;
  timestamp: string;
  event_data: Record<string, any>;
  event_source: {
    id: number;
    name: string;
    description: string;
  };
}

export interface RealTimeMetrics {
  project_name: string;
  current_hour_events: number;
  current_day_events: number;
  last_24h_events: number;
  active_users_today: number;
  active_sessions_now: number;
  top_events_today: [string, number][];
  event_sources: EventSource[];
  last_updated: string;
}

export interface EventSource {
  id: number;
  name: string;
  description: string;
  created_at?: string;
}

export interface AggregationData {
  id: number;
  event_name: string;
  event_count: number;
  unique_users: number;
  event_source: EventSource;
}

export interface DailyAggregation extends AggregationData {
  date: string;
}

export interface HourlyAggregation extends AggregationData {
  datetime_hour: string;
}

export interface FiveMinuteAggregation extends AggregationData {
  datetime_5min: string;
}

export interface FilterParams {
  start_date?: string;
  end_date?: string;
  event_name?: string;
  event_source_id?: number;
  user_id?: string;
}
