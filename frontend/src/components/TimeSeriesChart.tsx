import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { format, parseISO } from 'date-fns';
import { FilterParams, HourlyAggregation, FiveMinuteAggregation } from '../types';
import { analyticsApi } from '../services/api';

interface TimeSeriesChartProps {
  filters: FilterParams;
}

type ChartType = 'hourly' | '5min';
type ViewType = 'events' | 'users';

const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({ filters }) => {
  const [chartData, setChartData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chartType, setChartType] = useState<ChartType>('hourly');
  const [viewType, setViewType] = useState<ViewType>('events');
  const [chartStyle, setChartStyle] = useState<'line' | 'bar'>('line');

  const loadChartData = async () => {
    try {
      setLoading(true);
      setError(null);

      let data;
      if (chartType === '5min') {
        const response = await analyticsApi.getFiveMinuteAggregations(filters);
        data = response.results.map((item: FiveMinuteAggregation) => ({
          timestamp: item.datetime_5min,
          events: item.event_count,
          users: item.unique_users,
          event_name: item.event_name,
          source: item.event_source.name,
          formatted_time: format(parseISO(item.datetime_5min), 'HH:mm'),
          full_time: format(parseISO(item.datetime_5min), 'yyyy-MM-dd HH:mm')
        }));
      } else {
        const response = await analyticsApi.getHourlyAggregations(filters);
        data = response.results.map((item: HourlyAggregation) => ({
          timestamp: item.datetime_hour,
          events: item.event_count,
          users: item.unique_users,
          event_name: item.event_name,
          source: item.event_source.name,
          formatted_time: format(parseISO(item.datetime_hour), 'MM-dd HH:mm'),
          full_time: format(parseISO(item.datetime_hour), 'yyyy-MM-dd HH:mm')
        }));
      }

      // Sort by timestamp and take most recent data
      data.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
      setChartData(data.slice(-50)); // Limit to last 50 data points
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chart data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadChartData();
  }, [filters, chartType, loadChartData]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="terminal-border bg-black p-3 text-sm">
          <div className="text-green-400 font-bold mb-1">{label}</div>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="text-green-300">
              <span className="text-green-400">{entry.dataKey.toUpperCase()}:</span> {entry.value.toLocaleString()}
            </div>
          ))}
          {payload[0]?.payload?.event_name && (
            <div className="text-green-200 text-xs mt-1">
              Event: {payload[0].payload.event_name}
            </div>
          )}
          {payload[0]?.payload?.source && (
            <div className="text-green-200 text-xs">
              Source: {payload[0].payload.source}
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  const renderChart = () => {
    const dataKey = viewType === 'events' ? 'events' : 'users';
    const color = viewType === 'events' ? '#00ff00' : '#00ffff';

    if (chartStyle === 'bar') {
      return (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#003300" />
            <XAxis
              dataKey="formatted_time"
              stroke="#00ff00"
              fontSize={10}
              tick={{ fill: '#00ff00' }}
            />
            <YAxis
              stroke="#00ff00"
              fontSize={10}
              tick={{ fill: '#00ff00' }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey={dataKey} fill={color} stroke={color} />
          </BarChart>
        </ResponsiveContainer>
      );
    }

    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#003300" />
          <XAxis
            dataKey="formatted_time"
            stroke="#00ff00"
            fontSize={10}
            tick={{ fill: '#00ff00' }}
          />
          <YAxis
            stroke="#00ff00"
            fontSize={10}
            tick={{ fill: '#00ff00' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            dot={{ fill: color, strokeWidth: 2, r: 3 }}
            activeDot={{ r: 5, stroke: color, strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  };

  return (
    <div className="terminal-border p-4 bg-black">
      {/* Chart Header */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-bold terminal-glow text-green-400">TIME_SERIES_ANALYSIS</h2>
        <div className="text-xs text-green-300">
          DATA_POINTS: {chartData.length} | STATUS: {loading ? 'LOADING' : 'READY'}
        </div>
      </div>

      {/* Chart Controls */}
      <div className="flex flex-wrap gap-4 mb-4 text-sm">
        {/* Time Resolution */}
        <div className="flex space-x-2">
          <span className="text-green-300">RESOLUTION:</span>
          {(['hourly', '5min'] as ChartType[]).map((type) => (
            <button
              key={type}
              onClick={() => setChartType(type)}
              className={`px-3 py-1 terminal-border ${
                chartType === type
                  ? 'bg-green-900 bg-opacity-20 text-green-400'
                  : 'bg-transparent text-green-300 hover:bg-green-900 hover:bg-opacity-10'
              }`}
            >
              {type.toUpperCase()}
            </button>
          ))}
        </div>

        {/* View Type */}
        <div className="flex space-x-2">
          <span className="text-green-300">METRIC:</span>
          {(['events', 'users'] as ViewType[]).map((type) => (
            <button
              key={type}
              onClick={() => setViewType(type)}
              className={`px-3 py-1 terminal-border ${
                viewType === type
                  ? 'bg-green-900 bg-opacity-20 text-green-400'
                  : 'bg-transparent text-green-300 hover:bg-green-900 hover:bg-opacity-10'
              }`}
            >
              {type.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Chart Style */}
        <div className="flex space-x-2">
          <span className="text-green-300">STYLE:</span>
          {(['line', 'bar'] as const).map((style) => (
            <button
              key={style}
              onClick={() => setChartStyle(style)}
              className={`px-3 py-1 terminal-border ${
                chartStyle === style
                  ? 'bg-green-900 bg-opacity-20 text-green-400'
                  : 'bg-transparent text-green-300 hover:bg-green-900 hover:bg-opacity-10'
              }`}
            >
              {style.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Content */}
      <div className="terminal-border bg-black p-4">
        {loading && (
          <div className="flex items-center justify-center h-64">
            <div className="text-green-400 terminal-glow">
              <span className="blink">█</span> Loading chart data...
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="text-red-400 terminal-glow mb-2">CHART_ERROR:</div>
              <div className="text-red-300 text-sm">{error}</div>
              <button
                onClick={loadChartData}
                className="mt-4 px-4 py-2 terminal-border bg-transparent text-green-400 hover:bg-green-900 hover:bg-opacity-20"
              >
                RETRY
              </button>
            </div>
          </div>
        )}

        {!loading && !error && chartData.length === 0 && (
          <div className="flex items-center justify-center h-64">
            <div className="text-green-300 terminal-glow">NO_DATA_AVAILABLE</div>
          </div>
        )}

        {!loading && !error && chartData.length > 0 && renderChart()}
      </div>

      {/* Chart Footer */}
      {chartData.length > 0 && (
        <div className="mt-2 text-xs text-green-300 flex justify-between">
          <div>
            RANGE: {chartData[0]?.full_time} → {chartData[chartData.length - 1]?.full_time}
          </div>
          <div>
            TOTAL_{viewType.toUpperCase()}: {chartData.reduce((sum, item) => sum + (viewType === 'events' ? item.events : item.users), 0).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  );
};

export default TimeSeriesChart;
