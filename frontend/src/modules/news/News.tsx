import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../core/api';

interface Preferences { daily_limit: number; reduce_crime: boolean; excluded_keywords: string[] }
interface Story { id: string; title: string; excerpt: string; source: string; category: 'malaysia' | 'world' | 'discovery'; published_at: string; url: string; read: boolean }
interface Briefing { date: string; items: Story[]; total: number; read_count: number; caught_up: boolean; unavailable_sources: string[]; preferences: Preferences }
const categories = { malaysia: 'Malaysia', world: 'World', discovery: 'Discovery' };

export function NewsToday() {
  return <div className="activity-card news-today"><span className="activity-icon">▧</span><div><strong>Daily briefing</strong><p>Malaysia, the world & a little discovery.</p></div>
    <button className="secondary" onClick={() => window.dispatchEvent(new Event('open-news'))}>Open news</button></div>;
}

export function NewsPage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  async function load() { setBriefing(await api<Briefing>('/news/briefing')); }
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (error) { setError(error instanceof Error ? error.message : 'Could not load news.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { void run(load); }, []);
  useEffect(() => {
    if (!briefing) return;
    const timer = setInterval(() => {
      const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kuala_Lumpur', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
      if (today !== briefing.date) void run(load);
    }, 60000);
    return () => clearInterval(timer);
  }, [briefing?.date]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    await run(async () => {
      await api('/news/preferences', { method: 'PUT', body: JSON.stringify({
        daily_limit: Number(form.get('limit')), reduce_crime: form.has('crime'),
        excluded_keywords: String(form.get('excluded')).split(/[,\n]/).map(word => word.trim()).filter(Boolean),
      }) });
      await load(); setNotice('Preferences saved. New stories and higher limits apply to your next daily briefing.');
    });
  }
  return <section className="news-page"><div className="page-heading"><div><span className="eyebrow">A LITTLE CONTEXT, THEN BACK TO YOUR DAY</span><h1>Daily briefing</h1>
    <p>Malaysia · World · Discovery</p></div><span className="badge">Free RSS</span></div>
    {error && <p className="banner error" role="alert">{error} <button className="text-button" disabled={busy} onClick={() => void run(load)}>Retry</button></p>}
    {notice && <p className="banner" role="status">{notice}</p>}
    {!briefing ? !error && <p role="status">{busy ? 'Gathering your briefing…' : 'No briefing loaded.'}</p> : <>
      <div className="briefing-summary"><strong>{briefing.read_count} / {briefing.total} stories read</strong><span>{briefing.date} · Malaysia time</span></div>
      {briefing.unavailable_sources.length > 0 && <p className="muted small">Some feeds are temporarily unavailable: {briefing.unavailable_sources.join(', ')}. Available stories are still shown.</p>}
      {briefing.items.length === 0 ? <div className="empty-state"><h2>No matching stories available yet.</h2><p>Feeds may be unavailable, or your exclusions may have filtered them out. Try again later.</p>
        <button className="secondary" disabled={busy} onClick={() => void run(load)}>Check available feeds</button></div> : <div className="news-stories">{briefing.items.map((story, index) =>
        <article className={`news-story ${story.read ? 'is-read' : ''}`} key={story.id}><div className="story-number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</div><div className="story-content">
          <div className="story-meta"><span className={`story-category ${story.category}`}>{categories[story.category]}</span><strong>{story.source}</strong><time dateTime={story.published_at}>{new Intl.DateTimeFormat('en-MY', { timeZone: 'Asia/Kuala_Lumpur', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(story.published_at))}</time></div>
          <h2><a href={story.url} target="_blank" rel="noopener noreferrer">{story.title}</a></h2>{story.excerpt && <p>{story.excerpt}</p>}
          <div className="story-actions"><a href={story.url} target="_blank" rel="noopener noreferrer">Read at {story.source} ↗</a>
            <label><input type="checkbox" checked={story.read} disabled={busy} aria-label={`Mark story ${index + 1} read`} onChange={() => void run(async () => {
              await api(`/news/stories/${story.id}/read`, { method: 'PUT', body: JSON.stringify({ read: !story.read }) }); await load();
            })} />Read</label></div>
        </div></article>)}</div>}
      {briefing.items.length > 0 && <div className="briefing-end"><span aria-hidden="true">✓</span><h2>{briefing.caught_up ? 'You’re caught up.' : 'That’s today’s briefing.'}</h2><p>No more stories today. Make room for the rest of your day.</p></div>}
      <details className="news-preferences"><summary>Briefing preferences</summary><form onSubmit={save} key={JSON.stringify(briefing.preferences)}>
        <label>Stories per day<select name="limit" defaultValue={briefing.preferences.daily_limit}>{[5, 6, 7, 8, 9, 10].map(value => <option value={value} key={value}>{value} stories</option>)}</select></label>
        <label className="reminder-toggle"><input name="crime" type="checkbox" defaultChecked={briefing.preferences.reduce_crime} />Reduce crime coverage</label>
        <label>Exclude words or phrases<textarea name="excluded" defaultValue={briefing.preferences.excluded_keywords.join('\n')} placeholder="One phrase per line, or separated by commas" /></label>
        <p className="muted small">Keyword/category filtering is imperfect. Changes can hide stories immediately; they won’t add another batch today.</p>
        <button className="primary" disabled={busy}>Save news preferences</button>
      </form></details>
    </>}
    <footer className="news-footer">Headlines and available excerpts from public RSS feeds. Read full articles at their publishers; some may require a subscription. No paid APIs or AI services.</footer>
  </section>;
}
