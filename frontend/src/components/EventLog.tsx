import React, { useState, useEffect, useRef } from 'react';
import { format, parseISO } from 'date-fns';
import { FilterParams, Event } from '../types';
import { analyticsApi } from '../services/api';

interface EventLogProps {
  filters: FilterParams;
}

const EventLog: React.FC<EventLogProps> = ({ filters }) => {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const logContainerRef = useRef<HTMLDivElement>(null);

  const loadEvents = async (_pageNum = 1, append = false) => {
    try {
      setLoading(true);
      setError(null);

      const response = await analyticsApi.getEvents({
        ...filters,
      });

      if (append) {
        setEvents(prev => [...prev, ...response.results]);
      } else {
        setEvents(response.results);
      }

      setTotalCount(response.count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setPage(1);
    loadEvents(1, false);
  }, [filters]);

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  const loadMoreEvents = () => {
    const nextPage = page + 1;
    setPage(nextPage);
    loadEvents(nextPage, true);
  };

  const formatEventData = (data: Record<string, any>) => {
    try {
      return JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  };

  const getEventTypeColor = (eventName: string) => {
    const hash = eventName.split('').reduce((a, b) => {
      a = ((a << 5) - a) + b.charCodeAt(0);
      return a & a;
    }, 0);

    const colors = [
      'text-green-400', 'text-blue-400', 'text-yellow-400',
      'text-purple-400', 'text-pink-400', 'text-cyan-400'
    ];

    return colors[Math.abs(hash) % colors.length];
  };

  return (
    <div className="terminal-border p-4 bg-black">
      {/* Event Log Header */}
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="text-lg font-bold terminal-glow text-green-400">EVENT_LOG</h2>
          <div className="text-sm text-green-300">
            SHOWING: {events.length.toLocaleString()} / {totalCount.toLocaleString()} EVENTS
          </div>
        </div>
        <div className="flex items-center space-x-4 text-sm">
          <label className="flex items-center space-x-2 text-green-300">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="terminal-border bg-black"
            />
            <span>AUTO_SCROLL</span>
          </label>
          <div className="text-green-300">
            STATUS: {loading ? 'LOADING' : 'READY'}
          </div>
        </div>
      </div>

      {/* Event Log Content */}
      <div
        ref={logContainerRef}
        className="terminal-border bg-black p-4 h-96 overflow-y-auto space-y-2 font-mono text-sm"
        style={{ scrollBehavior: autoScroll ? 'smooth' : 'auto' }}
      >
        {loading && events.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-green-400 terminal-glow">
              <span className="blink">█</span> Loading event log...
            </div>
          </div>
        )}

        {error && (
          <div className="text-center py-8">
            <div className="text-red-400 terminal-glow mb-2">LOG_ERROR:</div>
            <div className="text-red-300 text-sm">{error}</div>
            <button
              onClick={() => loadEvents(1, false)}
              className="mt-4 px-4 py-2 terminal-border bg-transparent text-green-400 hover:bg-green-900 hover:bg-opacity-20"
            >
              RETRY
            </button>
          </div>
        )}

        {!loading && !error && events.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-green-300 terminal-glow">NO_EVENTS_FOUND</div>
          </div>
        )}

        {events.map((event, index) => (
          <div key={`${event.id}-${index}`} className="terminal-border p-3 bg-black hover:bg-green-900 hover:bg-opacity-10">
            <div className="flex justify-between items-start mb-2">
              <div className="flex items-center space-x-3">
                <span className="text-green-400 font-bold">#{event.id}</span>
                <span className={`font-bold ${getEventTypeColor(event.event_name)}`}>
                  {event.event_name}
                </span>
                <span className="text-green-300 text-xs">
                  SRC:{event.event_source.name}
                </span>
              </div>
              <span className="text-green-200 text-xs">
                {format(parseISO(event.timestamp), 'yyyy-MM-dd HH:mm:ss')}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-green-300">USER_ID:</span>
                <span className="text-green-400 ml-2">{event.user_id || 'N/A'}</span>
              </div>
              <div>
                <span className="text-green-300">SESSION_ID:</span>
                <span className="text-green-400 ml-2">{event.session_id || 'N/A'}</span>
              </div>
              <div>
                <span className="text-green-300">SOURCE:</span>
                <span className="text-green-400 ml-2">{event.event_source.name}</span>
              </div>
            </div>

            {event.event_data && Object.keys(event.event_data).length > 0 && (
              <details className="mt-2">
                <summary className="text-green-300 cursor-pointer hover:text-green-400 text-xs">
                  EVENT_DATA ▼
                </summary>
                <pre className="mt-2 p-2 terminal-border bg-black text-green-200 text-xs overflow-x-auto">
                  {formatEventData(event.event_data)}
                </pre>
              </details>
            )}
          </div>
        ))}

        {/* Load More Button */}
        {events.length < totalCount && !loading && (
          <div className="text-center py-4">
            <button
              onClick={loadMoreEvents}
              className="px-6 py-2 terminal-border bg-transparent text-green-400 hover:bg-green-900 hover:bg-opacity-20"
            >
              LOAD_MORE_EVENTS ({totalCount - events.length} remaining)
            </button>
          </div>
        )}

        {loading && events.length > 0 && (
          <div className="text-center py-4 text-green-400 terminal-glow">
            <span className="blink">█</span> Loading more events...
          </div>
        )}
      </div>

      {/* Event Log Footer */}
      <div className="mt-4 flex justify-between items-center text-xs text-green-300">
        <div>
          FILTER_ACTIVE: {Object.values(filters).filter(v => v !== undefined && v !== '').length > 0 ? 'YES' : 'NO'}
        </div>
        <div>
          LAST_UPDATE: {new Date().toLocaleTimeString()}
        </div>
        <div>
          MEMORY_USAGE: {events.length} EVENTS_CACHED
        </div>
      </div>
    </div>
  );
};

export default EventLog;
