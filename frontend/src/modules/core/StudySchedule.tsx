import { api } from './api';
import { useEffect, useRef, useState } from 'react';

const defaultSchedule = [
  ['ITT610 · Network Security / Security Analysis', 'ICT652 · Ethical, Social and Professional Issues in ICT', 'Assignment Buffer'],
  ['AWS CloudIgnite Program'],
  ['ITT585 · Network Infrastructure Security'],
  ['AWS CloudIgnite Program'],
  ['ICT652 · Ethical, Social and Professional Issues in ICT'],
  ['ITT610 · Network Security / Security Analysis', 'ITT593 · Introduction to Digital Forensics'],
  ['ITT640 · Wireless Networks', 'ITT585 · Network Infrastructure Security'],
];

function malaysiaDate() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kuala_Lumpur', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const part = (type: string) => parts.find(value => value.type === type)!.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

export function StudySchedule() {
  const [schedule, setSchedule] = useState(defaultSchedule);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api<{ days: string[][] | null }>('/core/study-schedule').then(value => setSchedule(value.days || defaultSchedule)).catch(() => setError('Could not load your saved schedule.'));
  }, []);
  const [today, setToday] = useState(malaysiaDate);
  const [offset, setOffset] = useState(0);
  const touch = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => {
    const timer = window.setInterval(() => setToday(malaysiaDate()), 30000);
    return () => clearInterval(timer);
  }, []);
  const date = new Date(`${today}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  const heading = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'short' }).format(date);
  return <><section className="study-schedule" aria-label="Study schedule" tabIndex={0}
    onKeyDown={event => {
      if (event.target !== event.currentTarget) return;
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault(); setOffset(value => value + (event.key === 'ArrowRight' ? 1 : -1));
      }
    }}
    onTouchStart={event => { const point = event.touches[0]; touch.current = { x: point.clientX, y: point.clientY }; }}
    onTouchEnd={event => {
      const start = touch.current; touch.current = null;
      const end = event.changedTouches[0];
      if (!start || !end) return;
      const dx = end.clientX - start.x, dy = end.clientY - start.y;
      if (Math.abs(dx) >= 45 && Math.abs(dx) > Math.abs(dy)) setOffset(value => value + (dx < 0 ? 1 : -1));
    }} onTouchCancel={() => { touch.current = null; }}>
    <button className="icon-button" aria-label="Previous study day" onClick={() => setOffset(value => value - 1)}>‹</button>
    <div className="study-schedule-content" aria-live="polite" aria-atomic="true">
      <div className="study-schedule-date"><strong>{offset === 0 ? 'Study today' : offset === -1 ? 'Yesterday' : offset === 1 ? 'Tomorrow' : 'Study schedule'}</strong><span>{heading}</span></div>
      <ul>{!schedule[date.getUTCDay()].length && <li>No study planned</li>}{schedule[date.getUTCDay()].map(subject => <li key={subject}>{subject}</li>)}</ul>
    </div>
    {offset !== 0 && <button className="text-button study-schedule-reset" onClick={() => setOffset(0)}>Today</button>}
    <button className="icon-button" aria-label="Edit study schedule" onClick={() => { setDraft(schedule.map(day => day.join('\n'))); setEditing(!editing); }}>&#9881;</button>
    <button className="icon-button" aria-label="Next study day" onClick={() => setOffset(value => value + 1)}>›</button>
  </section>
  {error && <p className="error" role="alert">{error}</p>}
  {editing && <form className="study-schedule-editor" onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const days = draft.map(day => day.split(/\r?\n/).map(item => item.trim()).filter(Boolean));
      const saved = await api<{ days: string[][] }>('/core/study-schedule', { method: 'PUT', body: JSON.stringify({ days }) });
      setSchedule(saved.days); setEditing(false);
    } catch { setError('Could not save the schedule. Check your connection and use up to 20 entries per day, each at most 200 characters.'); }
    finally { setBusy(false); }
  }}><h2>Edit weekly study schedule</h2><p className="muted small">One subject or activity per line. Leave a day empty for no planned study.</p>
    <div className="study-schedule-fields">{[1, 2, 3, 4, 5, 6, 0].map(day => <label key={day}>{['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][day]}
      <textarea aria-label={['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][day]} rows={3} value={draft[day]} onChange={event => setDraft(previous => previous.map((value, index) => index === day ? event.target.value : value))} /></label>)}</div>
    <button className="primary" disabled={busy}>{busy ? 'Saving...' : 'Save study schedule'}</button>{' '}
    <button type="button" className="secondary" disabled={busy} onClick={() => setEditing(false)}>Cancel</button>
  </form>}</>;
}
