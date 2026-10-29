import { useEffect, useState } from 'react';
import { api } from './api';

interface Stats {
  completions: number;
  active_days: number;
  days: { date: string; completions: number }[];
}

export function HistoryPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    api<Stats>('/core/stats').then(setStats).catch(error => setError(error.message));
  }, []);
  return <section><div className="page-heading"><div><span className="eyebrow">YOUR RECORDED ACTIVITY</span><h1>Activity history</h1></div></div>
    {error && <p className="banner error" role="alert">{error}</p>}
    {stats ? <section className="activity-history"><p className="muted">{stats.completions} completed activities · {stats.active_days} active dates</p>
      <div className="activity-heatmap" aria-label="Activity history for the last 365 UTC dates">{stats.days.map(day => <span key={day.date} className={day.completions ? 'has-activity' : ''} title={`${day.date}: ${day.completions} activities`} />)}</div>
      <p className="muted small">Last 365 UTC dates. No daily target or attendance requirement.</p>
    </section> : !error && <p role="status">Loading activity history…</p>}
  </section>;
}
