import React from 'react';
import { RealTimeMetrics } from '../types';

interface MetricsPanelProps {
  metrics: RealTimeMetrics;
}

const MetricsPanel: React.FC<MetricsPanelProps> = ({ metrics }) => {
  const metricCards = [
    {
      label: 'CURRENT_HOUR',
      value: metrics.current_hour_events,
      unit: 'events',
      color: 'text-cyan-400',
    },
    {
      label: 'TODAY_TOTAL',
      value: metrics.current_day_events,
      unit: 'events',
      color: 'text-green-400',
    },
    {
      label: 'LAST_24H',
      value: metrics.last_24h_events,
      unit: 'events',
      color: 'text-yellow-400',
    },
    {
      label: 'ACTIVE_USERS',
      value: metrics.active_users_today,
      unit: 'users',
      color: 'text-blue-400',
    },
    {
      label: 'LIVE_SESSIONS',
      value: metrics.active_sessions_now,
      unit: 'sessions',
      color: 'text-red-400',
    },
  ];

  return (
    <div className="space-y-4">
      {/* Main Metrics */}
      <div className="terminal-border p-4 bg-black">
        <h2 className="text-lg font-bold terminal-glow text-green-400 mb-4">REAL-TIME METRICS</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {metricCards.map((metric) => (
            <div key={metric.label} className="terminal-border p-3 bg-black">
              <div className="text-xs text-green-300 mb-1">{metric.label}:</div>
              <div className={`text-2xl font-bold terminal-glow ${metric.color}`}>
                {metric.value.toLocaleString()}
              </div>
              <div className="text-xs text-green-200">{metric.unit}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Top Events & Sources */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Events Today */}
        <div className="terminal-border p-4 bg-black">
          <h3 className="text-md font-bold terminal-glow text-green-400 mb-3">TOP_EVENTS_TODAY</h3>
          {metrics.top_events_today.length > 0 ? (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {metrics.top_events_today.map(([eventName, count], index) => (
                <div key={eventName} className="flex justify-between items-center text-sm">
                  <div className="flex items-center space-x-2">
                    <span className="text-green-300 w-6 text-right">{index + 1}.</span>
                    <span className="text-green-400 font-mono truncate">{eventName}</span>
                  </div>
                  <span className="text-cyan-400 font-bold">{count.toLocaleString()}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-green-300 text-sm">NO_DATA_AVAILABLE</div>
          )}
        </div>

        {/* Event Sources */}
        <div className="terminal-border p-4 bg-black">
          <h3 className="text-md font-bold terminal-glow text-green-400 mb-3">EVENT_SOURCES</h3>
          {metrics.event_sources.length > 0 ? (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {metrics.event_sources.map((source, index) => (
                <div key={source.id} className="text-sm">
                  <div className="flex items-center space-x-2">
                    <span className="text-green-300 w-6 text-right">{index + 1}.</span>
                    <span className="text-green-400 font-mono">{source.name}</span>
                    <span className="text-green-600">#{source.id}</span>
                  </div>
                  {source.description && (
                    <div className="text-green-200 text-xs ml-8 truncate">{source.description}</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-green-300 text-sm">NO_SOURCES_CONFIGURED</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MetricsPanel;
