import axios from 'axios';
import { Event, RealTimeMetrics, DailyAggregation, HourlyAggregation, FiveMinuteAggregation, FilterParams, EventSource } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const API_KEY = process.env.REACT_APP_API_KEY || '';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/events/`,
  headers: {
    'Authorization': `Bearer ${API_KEY}`,
    'Content-Type': 'application/json',
  },
});

export const analyticsApi = {
  // Real-time metrics
  getRealTimeMetrics: async (): Promise<RealTimeMetrics> => {
    const response = await api.get('metrics/realtime/');
    return response.data;
  },

  // Event querying
  getEvents: async (params?: FilterParams): Promise<{ results: Event[], count: number }> => {
    const response = await api.get('query/', { params });
    return response.data;
  },

  // Event names and sources
  getEventNames: async (): Promise<{ event_names: string[], count: number }> => {
    const response = await api.get('names/');
    return response.data;
  },

  getEventSources: async (): Promise<{ event_sources: EventSource[], count: number }> => {
    const response = await api.get('sources/');
    return response.data;
  },

  // Aggregations
  getDailyAggregations: async (params?: FilterParams): Promise<{ results: DailyAggregation[], count: number }> => {
    const response = await api.get('aggregations/daily/', { params });
    return response.data;
  },

  getHourlyAggregations: async (params?: FilterParams): Promise<{ results: HourlyAggregation[], count: number }> => {
    const response = await api.get('aggregations/hourly/', { params });
    return response.data;
  },

  getFiveMinuteAggregations: async (params?: FilterParams): Promise<{ results: FiveMinuteAggregation[], count: number }> => {
    const response = await api.get('aggregations/5min/', { params });
    return response.data;
  },
};
