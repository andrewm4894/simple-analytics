import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { FilterParams, EventSource } from '../types';
import { analyticsApi } from '../services/api';

interface FiltersPanelProps {
  filters: FilterParams;
  onFiltersChange: (filters: FilterParams) => void;
  availableEventNames: string[];
  availableEventSources: EventSource[];
}

const FiltersPanel: React.FC<FiltersPanelProps> = ({
  filters,
  onFiltersChange,
  availableEventSources
}) => {
  const [eventNames, setEventNames] = useState<string[]>([]);
  const [loadingEventNames, setLoadingEventNames] = useState(false);

  useEffect(() => {
    const loadEventNames = async () => {
      try {
        setLoadingEventNames(true);
        const data = await analyticsApi.getEventNames();
        setEventNames(data.event_names);
      } catch (err) {
        console.error('Failed to load event names:', err);
      } finally {
        setLoadingEventNames(false);
      }
    };

    loadEventNames();
  }, []);

  const handleInputChange = (field: keyof FilterParams, value: string | number | undefined) => {
    onFiltersChange({
      ...filters,
      [field]: value || undefined,
    });
  };

  const presetRanges = [
    { label: 'LAST 1H', hours: 1 },
    { label: 'LAST 4H', hours: 4 },
    { label: 'LAST 24H', hours: 24 },
    { label: 'LAST 7D', hours: 24 * 7 },
  ];

  const setPresetRange = (hours: number) => {
    const end = new Date();
    const start = new Date(end.getTime() - hours * 60 * 60 * 1000);

    onFiltersChange({
      ...filters,
      start_date: format(start, "yyyy-MM-dd'T'HH:mm:ss"),
      end_date: format(end, "yyyy-MM-dd'T'HH:mm:ss"),
    });
  };

  const clearFilters = () => {
    onFiltersChange({
      start_date: format(new Date(Date.now() - 24 * 60 * 60 * 1000), "yyyy-MM-dd'T'HH:mm:ss"),
      end_date: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss"),
    });
  };

  return (
    <div className="terminal-border p-4 bg-black space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold terminal-glow text-green-400">FILTERS</h2>
        <button
          onClick={clearFilters}
          className="px-3 py-1 text-xs terminal-border bg-transparent text-yellow-400 hover:bg-yellow-900 hover:bg-opacity-20"
        >
          CLEAR
        </button>
      </div>

      {/* Time Range Presets */}
      <div className="space-y-2">
        <label className="block text-sm font-bold text-green-300">QUICK RANGE:</label>
        <div className="flex flex-wrap gap-2">
          {presetRanges.map((preset) => (
            <button
              key={preset.label}
              onClick={() => setPresetRange(preset.hours)}
              className="px-3 py-1 text-xs terminal-border bg-transparent text-green-400 hover:bg-green-900 hover:bg-opacity-20"
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Start Date */}
        <div className="space-y-2">
          <label className="block text-sm font-bold text-green-300">START_DATE:</label>
          <input
            type="datetime-local"
            value={filters.start_date ? filters.start_date.slice(0, 16) : ''}
            onChange={(e) => handleInputChange('start_date', e.target.value ? e.target.value + ':00' : '')}
            className="w-full p-2 bg-black terminal-border text-green-400 text-sm font-mono focus:outline-none focus:shadow-lg"
          />
        </div>

        {/* End Date */}
        <div className="space-y-2">
          <label className="block text-sm font-bold text-green-300">END_DATE:</label>
          <input
            type="datetime-local"
            value={filters.end_date ? filters.end_date.slice(0, 16) : ''}
            onChange={(e) => handleInputChange('end_date', e.target.value ? e.target.value + ':00' : '')}
            className="w-full p-2 bg-black terminal-border text-green-400 text-sm font-mono focus:outline-none focus:shadow-lg"
          />
        </div>

        {/* Event Name */}
        <div className="space-y-2">
          <label className="block text-sm font-bold text-green-300">EVENT_NAME:</label>
          <select
            value={filters.event_name || ''}
            onChange={(e) => handleInputChange('event_name', e.target.value)}
            className="w-full p-2 bg-black terminal-border text-green-400 text-sm font-mono focus:outline-none focus:shadow-lg"
            disabled={loadingEventNames}
          >
            <option value="">ALL EVENTS</option>
            {eventNames.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          {loadingEventNames && (
            <div className="text-xs text-green-300">Loading events...</div>
          )}
        </div>

        {/* Event Source */}
        <div className="space-y-2">
          <label className="block text-sm font-bold text-green-300">EVENT_SOURCE:</label>
          <select
            value={filters.event_source_id || ''}
            onChange={(e) => handleInputChange('event_source_id', e.target.value ? parseInt(e.target.value) : undefined)}
            className="w-full p-2 bg-black terminal-border text-green-400 text-sm font-mono focus:outline-none focus:shadow-lg"
          >
            <option value="">ALL SOURCES</option>
            {availableEventSources.map((source) => (
              <option key={source.id} value={source.id}>{source.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* User ID Filter */}
      <div className="space-y-2">
        <label className="block text-sm font-bold text-green-300">USER_ID (optional):</label>
        <input
          type="text"
          value={filters.user_id || ''}
          onChange={(e) => handleInputChange('user_id', e.target.value)}
          placeholder="Filter by specific user ID..."
          className="w-full p-2 bg-black terminal-border text-green-400 text-sm font-mono focus:outline-none focus:shadow-lg placeholder-green-600"
        />
      </div>

      {/* Status */}
      <div className="text-xs text-green-300 mt-4">
        FILTER_STATUS: {Object.values(filters).filter(v => v !== undefined && v !== '').length} ACTIVE
      </div>
    </div>
  );
};

export default FiltersPanel;
