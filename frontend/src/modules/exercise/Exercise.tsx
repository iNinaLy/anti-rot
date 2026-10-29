import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../core/api';
import { enableExercisePush, disableExercisePush } from './push';

export interface ExercisePlan {
  name: string; total_days: number; workout_links: string[]; completed_count: number; progress_percent: number;
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
      plan.today_kind === 'walk' ? 'Walk' : plan.current_day > plan.total_days ? 'Challenge complete' : `Day ${plan.current_day}`}</p></div>
    <button className="secondary" onClick={openExercise}>Open exercise</button></div>;
}

export function ExercisePage({ onChange }: { onChange: () => Promise<void> }) {
  const [plan, setPlan] = useState<ExercisePlan | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [totalDays, setTotalDays] = useState(30);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [notice, setNotice] = useState('');
  useEffect(() => {
    api<ExercisePlan>('/exercise/plan').then(value => { setPlan(value); setTotalDays(value.total_days); }).catch(error => setError(error.message));
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
        name: String(data.get('name')).trim(), total_days: Number(data.get('total_days')),
        playlist_url: String(data.get('playlist_url')).trim(),
        workout_links: String(data.get('workout_links')).split(/\r?\n/).map(link => link.trim()).filter((link, index, links) => link || links.slice(index).some(Boolean)),
        current_day: Number(data.get('day')), weekdays: data.getAll('weekday').map(Number),
        reminder_time: data.get('time'), reminders: data.has('reminders'), version: plan.version,
      }) });
      setPlan(next); setNotice('Settings saved.'); await onChange();
    });
  }
  if (!plan) return <section><h1>Exercise</h1><p role={error ? 'alert' : 'status'}>{error || 'Loading…'}</p></section>;
  const finished = plan.current_day > plan.total_days;
  const title = plan.today_kind === 'walk' ? 'Walk' : plan.completed_today ? `Day ${plan.today_day}` : finished ? 'Challenge complete' : `Day ${plan.current_day}`;
  return <section className="exercise-page"><div className="page-heading"><div><span className="eyebrow">MOVE AT YOUR OWN PACE</span><h1>Exercise</h1></div>
    <button className="secondary" onClick={() => setSettingsOpen(!settingsOpen)}>{settingsOpen ? 'Back to dashboard' : 'Plan settings'}</button></div>
    {error && <p className="banner error" role="alert">{error} <button className="text-button" onClick={() => void run(async () => setPlan(await api<ExercisePlan>('/exercise/plan')))}>Reload</button></p>}
    {notice && <p className="banner" role="status">{notice}</p>}
    <div className="exercise-checklist"><label className="workout-check"><input type="checkbox" aria-label={`Complete ${title}`} checked={plan.completed_today}
      disabled={busy || plan.completed_today || (finished && plan.today_kind === 'strength')} onChange={() => void done()} /><span>{title}</span>
      <small>{plan.completed_today ? 'Completed' : 'Today'}</small></label>
      {plan.today_kind === 'strength' && !finished && plan.workout_url && <a className="primary" href={plan.workout_url} target="_blank" rel="noopener noreferrer">Watch on YouTube ↗</a>}
    </div>
    <section className="strength-progress" aria-label="Strength training progress"><h2>Strength training</h2><p>{plan.name}</p>
      <div className="strength-progress-summary"><strong>{plan.progress_percent}%</strong><span>{plan.completed_count} of {plan.total_days} sessions completed</span></div>
      <progress max={plan.total_days} value={plan.completed_count} aria-label="Strength challenge completion" />
      <p className="muted small">Walks are separate. Missed days never advance the plan.</p>
      {plan.playlist_url && <a href={plan.playlist_url} target="_blank" rel="noopener noreferrer">YouTube playlist ?</a>}
    </section>
    {settingsOpen && <form className="exercise-settings" onSubmit={save} key={plan.version}><h2>Strength plan settings</h2>
      <div className="exercise-settings-row"><label>Plan name<input name="name" defaultValue={plan.name} maxLength={120} required /></label>
        <label>Number of strength sessions<input type="number" name="total_days" min={1} max={365} value={totalDays} onChange={event => setTotalDays(Number(event.target.value))} required /></label></div>
      <label>YouTube playlist or video<input type="url" name="playlist_url" defaultValue={plan.playlist_url} placeholder="https://www.youtube.com/playlist?list=..." /></label>
      <label>Individual workout links (optional)<textarea name="workout_links" rows={4} defaultValue={plan.workout_links.join('\n')} placeholder="One YouTube link per session, in order" /></label>
      <p className="muted small">One line per strength session. Blank lines use the playlist. Editing this plan keeps its completed sessions; changing the next session does not mark skipped sessions complete.</p>
      <div className="exercise-settings-row"><label>Next challenge day<select name="day" defaultValue={plan.current_day}>{Array.from({ length: Math.max(1, Math.min(365, totalDays)) }, (_, index) => index + 1).map(day => <option key={day} value={day}>Day {day}</option>)}<option value={totalDays + 1}>Challenge complete</option></select></label>
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
    </form>}
  </section>;
}
