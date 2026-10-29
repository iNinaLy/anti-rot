import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../core/api';

interface Reward { id: string; name: string; cost: number }
interface Wallet { earned: number; spent: number; balance: number; rewards: Reward[]; history: { id:string; name:string; cost:number; redeemed_at:string }[] }

export function RewardsPage() {
  const [wallet, setWallet] = useState<Wallet | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Reward | null>(null);
  const [stats, setStats] = useState<{completions:number; points:number; active_days:number; days:{date:string; completions:number; points:number}[]} | null>(null);
  async function load() { const [value, history] = await Promise.all([api<Wallet>('/rewards'), api<typeof stats>('/core/stats')]); setWallet(value); setStats(history); }
  useEffect(() => { void load().catch(error => setError(error.message)); }, []);
  async function run(action: () => Promise<void>) {
    if (busy) return; setBusy(true); setError('');
    try { await action(); await load(); } catch (error) { setError(error instanceof Error ? error.message : 'Try again.'); }
    finally { setBusy(false); }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    await run(async () => { await api(`/rewards/items${editing ? '/'+editing.id : ''}`, { method: editing ? 'PUT' : 'POST', body: JSON.stringify({ name:form.get('name'), cost:Number(form.get('cost')) }) }); setEditing(null); });
  }
  return <section><div className="page-heading"><div><span className="eyebrow">YOUR LEARNING, YOUR REWARDS</span><h1>Rewards & history</h1></div><span className="badge">{wallet?.balance ?? 0} points available</span></div>
    {error && <p className="banner error" role="alert">{error}</p>}
    <p className="muted">Earn points from completed flashcard sessions and exercise. News earns no points.</p>
    <div className="reward-grid">{wallet?.rewards.map(reward => <article className="reward-item" key={reward.id}><h2>{reward.name}</h2><p>{reward.cost} points</p><div className="exercise-actions">
      <button className="primary" disabled={busy || wallet.balance < reward.cost} onClick={() => void run(async () => {
        if (!confirm(`Redeem “${reward.name}” for ${reward.cost} points?`)) return;
        setWallet(await api<Wallet>('/rewards/redeem', { method:'POST',body:JSON.stringify({ id:crypto.randomUUID(),reward_id:reward.id }) }));
      })}>Redeem</button><button className="text-button" onClick={() => setEditing(reward)}>Edit</button>
      <button className="text-button danger" disabled={busy} onClick={() => void run(async () => { if (confirm('Remove this reward? History is preserved.')) await api(`/rewards/items/${reward.id}`, { method:'DELETE' }); })}>Remove</button>
    </div></article>)}</div>
    <form className="exercise-settings" onSubmit={save} key={editing?.id || 'new'}><h2>{editing ? 'Edit reward' : 'Add a reward'}</h2>
      <div className="exercise-settings-row"><label>Reward name<input name="name" required maxLength={200} defaultValue={editing?.name || ''} placeholder="e.g. An episode of my favourite show" /></label><label>Point cost<input name="cost" type="number" min={1} max={1000000} required defaultValue={editing?.cost || 10} /></label></div>
      <button className="primary" disabled={busy}>Save reward</button>{editing && <button type="button" className="text-button" onClick={() => setEditing(null)}>Cancel edit</button>}</form>
    {wallet && wallet.history.length > 0 && <section className="reward-history"><h2>Redemption history</h2>{wallet.history.map(item => <p key={item.id}>{item.name} <span className="muted">· {item.cost} points · {new Date(item.redeemed_at).toLocaleDateString()}</span></p>)}</section>}
    {stats && <section className="activity-history"><h2>Recorded activity</h2><p className="muted">{stats.completions} completed activities · {stats.points} points earned · {stats.active_days} active dates</p>
      <div className="activity-heatmap" aria-label="Activity history for the last 365 UTC dates">{stats.days.map(day => <span key={day.date} className={day.completions ? 'has-activity' : ''} title={`${day.date}: ${day.completions} activities, ${day.points} points`} />)}</div><p className="muted small">Last 365 UTC dates. No daily target or attendance requirement.</p>
    </section>}
  </section>;
}
