import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { RealTimeMetrics, FilterParams } from '../types';
import { analyticsApi } from '../services/api';
import FiltersPanel from './FiltersPanel';
import MetricsPanel from './MetricsPanel';
import TimeSeriesChart from './TimeSeriesChart';
import EventLog from './EventLog';

const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<RealTimeMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterParams>({
    start_date: format(new Date(Date.now() - 24 * 60 * 60 * 1000), "yyyy-MM-dd'T'HH:mm:ss"),
    end_date: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss"),
  });

  const loadMetrics = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await analyticsApi.getRealTimeMetrics();
      setMetrics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
    const interval = setInterval(loadMetrics, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading && !metrics) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="terminal-glow text-green-400">
          <span className="blink">█</span> Loading dashboard...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="terminal-border bg-black p-6 rounded">
          <div className="text-red-400 terminal-glow mb-2">ERROR:</div>
          <div className="text-red-300">{error}</div>
          <button
            onClick={loadMetrics}
            className="mt-4 px-4 py-2 terminal-border bg-transparent text-green-400 hover:bg-green-900 hover:bg-opacity-20"
          >
            RETRY
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 space-y-4">
      {/* Header */}
      <div className="terminal-border p-4 bg-black">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold terminal-glow mb-1">
              ANALYTICS DASHBOARD - {metrics?.project_name?.toUpperCase() || 'UNKNOWN'}
            </h1>
            <div className="text-sm text-green-300">
              Last Updated: {metrics ? format(new Date(metrics.last_updated), 'yyyy-MM-dd HH:mm:ss') : '--'}
              <span className="ml-2 blink text-green-400">█</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-green-300">STATUS: ONLINE</div>
            <div className="text-xs text-green-200">REAL-TIME MODE</div>
          </div>
        </div>
      </div>

      {/* Metrics Panel */}
      {metrics && <MetricsPanel metrics={metrics} />}

      {/* Filters */}
      <FiltersPanel
        filters={filters}
        onFiltersChange={setFilters}
        availableEventNames={[]}
        availableEventSources={metrics?.event_sources || []}
      />

      {/* Time Series Chart */}
      <TimeSeriesChart filters={filters} />

      {/* Event Log */}
      <EventLog filters={filters} />
    </div>
  );
};

export default Dashboard;
