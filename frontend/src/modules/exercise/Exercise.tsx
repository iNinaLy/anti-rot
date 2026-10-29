import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../core/api';
import { enableExercisePush, disableExercisePush } from './push';

export interface ExercisePlan {
  current_day: number; weekdays: number[]; reminder_time: string; reminders: boolean; version: number;
  today_kind: 'strength' | 'walk'; today_date: string; completed_today: boolean; today_day: number | null;
  completed_days: number[]; playlist_url: string; workout_url: string;
}

function openExercise() { window.dispatchEvent(new Event('open-exercise')); }

export function ExerciseToday({ refresh }: { refresh: unknown }) {
  const [plan, setPlan] = useState<ExercisePlan | null>(null);
  useEffect(() => {
    let active = true;
    api<ExercisePlan>('/exercise/plan').then(value => { if (active) setPlan(value); }).catch(() => {});
    return () => { active = false; };
  }, [refresh]);
  return <div className="activity-card exercise-today"><span className="activity-icon">↗</span><div><strong>Exercise</strong>
    <p>{!plan ? 'Strength & walks' : plan.completed_today ? plan.today_kind === 'walk' ? 'Walk completed' : `Day ${plan.today_day} completed` :
      plan.today_kind === 'walk' ? 'Walk' : plan.current_day > 30 ? 'Challenge complete' : `Day ${plan.current_day}`}</p></div>
    <button className="secondary" onClick={openExercise}>Open exercise</button></div>;
}

export function ExercisePage({ onChange }: { onChange: () => Promise<void> }) {
  const [plan, setPlan] = useState<ExercisePlan | null>(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [notice, setNotice] = useState('');
  useEffect(() => {
    api<ExercisePlan>('/exercise/plan').then(setPlan).catch(error => setError(error.message));
  }, []);
  useEffect(() => {
    if (!plan) return;
    const timer = window.setInterval(() => {
      const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kuala_Lumpur', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
      if (today !== plan.today_date) api<ExercisePlan>('/exercise/plan').then(setPlan).catch(() => {});
    }, 60000);
    return () => clearInterval(timer);
  }, [plan?.today_date]);
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (error) { setError(error instanceof Error ? error.message : 'Try again.'); }
    finally { setBusy(false); }
  }
  async function done() {
    await run(async () => {
      if (!plan) return;
      const next = await api<ExercisePlan>('/exercise/complete', { method: 'POST', body: JSON.stringify({
        id: crypto.randomUUID(), kind: plan.today_kind, day: plan.today_kind === 'strength' ? plan.current_day : null,
        version: plan.version,
      }) });
      setPlan(next); await onChange();
    });
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    await run(async () => {
      if (!plan) return;
      const next = await api<ExercisePlan>('/exercise/plan', { method: 'PUT', body: JSON.stringify({
        current_day: Number(data.get('day')), weekdays: data.getAll('weekday').map(Number),
        reminder_time: data.get('time'), reminders: data.has('reminders'), version: plan.version,
      }) });
      setPlan(next); setNotice('Settings saved.'); await onChange();
    });
  }
  if (!plan) return <section><h1>Exercise</h1><p role={error ? 'alert' : 'status'}>{error || 'Loading…'}</p></section>;
  const finished = plan.current_day > 30;
  const title = plan.today_kind === 'walk' ? 'Walk' : plan.completed_today ? `Day ${plan.today_day}` : finished ? 'Challenge complete' : `Day ${plan.current_day}`;
  return <section className="exercise-page"><div className="page-heading"><div><span className="eyebrow">NOURISH MOVE LOVE · 30 DAYS</span><h1>Exercise</h1></div>
    <a className="secondary" href={plan.playlist_url} target="_blank" rel="noopener noreferrer">YouTube playlist ↗</a></div>
    {error && <p className="banner error" role="alert">{error} <button className="text-button" onClick={() => void run(async () => setPlan(await api<ExercisePlan>('/exercise/plan')))}>Reload</button></p>}
    {notice && <p className="banner" role="status">{notice}</p>}
    <div className="exercise-checklist"><label className="workout-check"><input type="checkbox" aria-label={`Complete ${title}`} checked={plan.completed_today}
      disabled={busy || plan.completed_today || (finished && plan.today_kind === 'strength')} onChange={() => void done()} /><span>{title}</span>
      <small>{plan.completed_today ? 'Completed' : 'Today'}</small></label>
      {plan.today_kind === 'strength' && !finished && <a className="primary" href={plan.workout_url} target="_blank" rel="noopener noreferrer">Watch on YouTube ↗</a>}
    </div>
    <div className="challenge-days" aria-label="Challenge progress">{Array.from({ length: 30 }, (_, index) => index + 1).map(day =>
      <span key={day} className={`challenge-day ${plan.completed_days.includes(day) ? 'completed' : ''} ${plan.current_day === day ? 'current' : ''}`}
        aria-label={`Day ${day}${plan.completed_days.includes(day) ? ', completed' : plan.current_day === day ? ', next' : ''}`}>Day {day}{plan.completed_days.includes(day) && <span aria-hidden="true"> ✓</span>}</span>)}</div>
    <form className="exercise-settings" onSubmit={save} key={plan.version}><h2>Schedule & reminders</h2>
      <div className="exercise-settings-row"><label>Next challenge day<select name="day" defaultValue={plan.current_day}>{Array.from({ length: 30 }, (_, index) => index + 1).map(day => <option key={day} value={day}>Day {day}</option>)}<option value={31}>Challenge complete</option></select></label>
        <label>Reminder time<input type="time" name="time" defaultValue={plan.reminder_time} required /></label></div>
      <fieldset><legend>Strength days</legend><div className="weekday-options">{['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((day, index) =>
        <label key={day}><input type="checkbox" name="weekday" value={index} defaultChecked={plan.weekdays.includes(index)} />{day}</label>)}</div></fieldset>
      <p className="muted small">Other days: walks. Timezone: Malaysia (UTC+8).</p>
      <label className="reminder-toggle"><input type="checkbox" name="reminders" defaultChecked={plan.reminders} />Reminders enabled</label>
      <div className="exercise-actions"><button className="primary" disabled={busy}>Save exercise settings</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => void run(async () => {
          await enableExercisePush();
          setPlan(await api<ExercisePlan>('/exercise/plan', { method: 'PUT', body: JSON.stringify({ ...plan, reminders: true }) }));
          setNotice('Notifications enabled on this device.');
        })}>Enable device notifications</button>
        <button type="button" className="text-button" disabled={busy} onClick={() => void run(async () => {
          await disableExercisePush(); setNotice('Notifications disabled on this device.');
        })}>Disable device notifications</button></div>
      <p className="muted small">Allow browser notifications. HTTPS or localhost required; iPhone requires Home Screen installation. The server must stay running.</p>
    </form>
  </section>;
}
