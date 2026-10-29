import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { api, authenticate, restoreSession, setToken } from './modules/core/api';
import { Today } from './modules/core/Today';
import { clearPrivateData, jobsFor, queueReview, readData, saveData } from './modules/core/storage';
import { cacheSessionImages, syncJobs } from './modules/flashcards/offline';
import { CardImages } from './modules/flashcards/CardImages';
import { groupBySubject } from './modules/flashcards/subjects';
import { SubjectSelect } from './modules/flashcards/SubjectSelect';
import { ExercisePage } from './modules/exercise/Exercise';
import { disableExercisePush } from './modules/exercise/push';
import { NewsPage } from './modules/news/News';
import { HistoryPage } from './modules/core/History';
import { DraftGenerator } from './modules/flashcards/DraftGenerator';
import type { Card, Deck, Rating, ReviewSession, Today as TodayType, User } from './types';

const emptyToday: TodayType = { streak: 0, points: 0, activities: [] };
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong';
const readyCount = (deck: Deck) => deck.ready_count ?? deck.due_count;
function intervalLabel(days: number): string {
  if (days < 1 / 24) return `${Math.max(1, Math.round(days * 1440))}m`;
  if (days < 1) return `${Math.round(days * 24)}h`;
  return `${Math.round(days)}d`;
}
function restoredUser(): User | null {
  try { return JSON.parse(localStorage.getItem('user') || 'null'); } catch { return null; }
}

function Modal({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
    window.addEventListener('keydown', handler);
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLDialogElement>('dialog');
    dialog?.showModal();
    return () => { window.removeEventListener('keydown', handler); previous?.focus(); };
  }, [close]);
  return <dialog onCancel={close} aria-label={title}><div className="modal-heading"><h2>{title}</h2>
    <button className="icon-button" onClick={close} aria-label="Close dialog">×</button></div>{children}</dialog>;
}

function Auth({ onUser }: { onUser: (user: User) => void }) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try { onUser(await authenticate(String(form.get('email')), String(form.get('password')))); }
    catch (error) { setError(errorMessage(error)); } finally { setBusy(false); }
  }
  return <main className="auth-layout"><div className="auth-story"><a className="brand" href="/"><img src="/anti-rot-logo.jpg" className="brand-logo" alt="" /><span>Anti-Rot</span></a>
    <span className="eyebrow">A LITTLE, EVERY DAY</span><h1>Good things<br />take remembering.</h1>
    <p>A quiet space to learn, revisit, and make knowledge stick.<br />One small session at a time.</p>
    <div className="sample-card"><span>YOUR NEXT SMALL DISCOVERY</span><p>What will you remember tomorrow?</p><div>Learn a little. Keep a lot. ↗</div></div>
    <small>Your learning. Your server. Your pace.</small></div>
    <div className="auth-form"><span className="eyebrow">WELCOME TO ANTI-ROT</span><h2>Pick up where you left off.</h2>
      <p className="muted">Sign in to your personal learning space.</p>
      <form onSubmit={submit}><label>Email<input name="email" type="email" autoComplete="email" required autoFocus /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" minLength={10} maxLength={128} required /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <small className="muted">You’ll stay signed in on this browser.</small>
        <button className="primary" disabled={busy}>{busy ? 'One moment…' : 'Sign in →'}</button>
      </form>
      {/* Sign-up intentionally disabled. Accounts are created locally through the CLI.
          <p className="auth-toggle"><button>Create an account</button></p>
      */}
    </div></main>;
}

export default function App() {
  const [user, setUser] = useState<User | null>(restoredUser);
  const [restoring, setRestoring] = useState(() => !restoredUser() && navigator.onLine);
  const [section, setSection] = useState(() => { const view = new URLSearchParams(location.search).get('view'); return ['exercise','news','history'].includes(view || '') ? view! : 'today'; });
  const exerciseOpen = section === 'exercise', newsOpen = section === 'news', historyOpen = section === 'history';
  useEffect(() => {
    const url = new URL(location.href);
    if (section !== 'today') url.searchParams.set('view', section);
    else url.searchParams.delete('view');
    history.replaceState(null, '', url);
  }, [section]);
  const [decks, setDecks] = useState<Deck[]>([]), [today, setToday] = useState(emptyToday);
  const [online, setOnline] = useState(navigator.onLine), [pending, setPending] = useState(0);
  const [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Deck | null>(null), [cards, setCards] = useState<Card[]>([]);
  const [session, setSession] = useState<ReviewSession | null>(null), [revealed, setRevealed] = useState(false);
  const [deckEditor, setDeckEditor] = useState<Deck | 'new' | null>(null);
  const [cardEditor, setCardEditor] = useState<Card | 'new' | null>(null);
  const [search, setSearch] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [reviewMode, setReviewMode] = useState<'recall' | 'choice'>('recall');
  const [pickedChoice, setPickedChoice] = useState<string | null>(null);
  const [reauth, setReauth] = useState(false);
  const closeDeck = useCallback(() => setDeckEditor(null), []);
  const closeCard = useCallback(() => setCardEditor(null), []);
  const closeReauth = useCallback(() => setReauth(false), []);
  useEffect(() => {
    const open = () => { setSection('exercise'); setSelected(null); };
    window.addEventListener('open-exercise', open);
    return () => window.removeEventListener('open-exercise', open);
  }, []);
  useEffect(() => {
    const open = () => { setSection('news'); setSelected(null); };
    window.addEventListener('open-news', open);
    return () => window.removeEventListener('open-news', open);
  }, []);
  useEffect(() => {
    const open = () => { setSection('history'); setSelected(null); };
    window.addEventListener('open-history', open);
    return () => window.removeEventListener('open-history', open);
  }, []);

  useEffect(() => {
    if (user || !navigator.onLine) { setRestoring(false); return; }
    let active = true;
    void restoreSession().then(next => {
      if (!active) return;
      if (next) { localStorage.setItem('user', JSON.stringify(next)); setUser(next); }
      setRestoring(false);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const required = () => setReauth(true);
    window.addEventListener('auth-required', required);
    return () => window.removeEventListener('auth-required', required);
  }, []);

  const loadDashboard = useCallback(async () => {
    if (!user) return;
    const cachedDecks = await readData<Deck[]>(user.id, 'decks');
    const cachedToday = await readData<TodayType>(user.id, 'today');
    if (cachedDecks) setDecks(cachedDecks);
    if (cachedToday) setToday(cachedToday);
    try {
      const [nextDecks, nextToday] = await Promise.all([api<Deck[]>('/flashcards/decks'), api<TodayType>('/core/today')]);
      setDecks(nextDecks); setToday(nextToday);
      await Promise.all([saveData(user.id, 'decks', nextDecks), saveData(user.id, 'today', nextToday)]);
    } catch (e) { if (navigator.onLine) setError(errorMessage(e)); }
    finally { setLoading(false); }
  }, [user]);

  const synchronize = useCallback(async () => {
    if (!user) return;
    try {
      setPending(await syncJobs(user.id));
      await loadDashboard();
    } catch (e) { setError(`Sync paused: ${errorMessage(e)}. Your pending reviews are saved on this device.`); }
    setPending((await jobsFor(user.id)).length);
  }, [user, loadDashboard]);

  useEffect(() => {
    if (!user) return;
    void loadDashboard();
    void readData<ReviewSession | null>(user.id, 'session').then(saved => setSession(saved || null));
    void jobsFor(user.id).then(jobs => setPending(jobs.length));
    if (navigator.onLine) void synchronize();
    const timer = window.setInterval(() => { if (navigator.onLine) void synchronize(); }, 60000);
    return () => window.clearInterval(timer);
  }, [user, loadDashboard, synchronize]);

  useEffect(() => {
    const connected = () => { setOnline(true); void synchronize(); };
    const disconnected = () => setOnline(false);
    window.addEventListener('online', connected); window.addEventListener('offline', disconnected);
    return () => { window.removeEventListener('online', connected); window.removeEventListener('offline', disconnected); };
  }, [synchronize]);

  function signedIn(next: User) { localStorage.setItem('user', JSON.stringify(next)); setUser(next); setError(''); }

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  async function signOut() {
    if (pending && !confirm('There are unsynced reviews. Signing out will remove them from this device. Sign out?')) return;
    await run(async () => {
      // Revoke the refresh cookie before clearing local state.
      await disableExercisePush().catch(() => {});
      await api('/core/auth/logout', { method: 'POST' });
      await clearPrivateData(); localStorage.removeItem('user'); setToken(''); setUser(null);
      setDecks([]); setToday(emptyToday); setSession(null); setSelected(null); setSection('today'); setPending(0);
    });
  }

  async function openDeck(deck: Deck) {
    await run(async () => {
      const next = await api<Card[]>(`/flashcards/decks/${deck.id}/cards`);
      setCards(next); setSelected(deck); setSection('today'); setSearch(''); setTagFilter('');
    });
  }

  async function start(deck: Deck) {
    await run(async () => {
      if (!user) return;
      if (session && !confirm('Replace your current session? Reviews already rated remain saved.')) return;
      if ((await jobsFor(user.id)).length) {
        if (await syncJobs(user.id)) throw new Error('Sync pending reviews before starting another session.');
      }
      const tag = selected?.id === deck.id ? tagFilter : '';
      const next = { ...await api<ReviewSession>(`/flashcards/decks/${deck.id}/sessions?limit=10${tag ? '&tag='+encodeURIComponent(tag) : ''}`, { method: 'POST' }), index: 0 };
      // A session is marked offline-ready only after every attachment is cached.
      await cacheSessionImages(user.id, next);
      await saveData(user.id, 'session', next);
      setSession(next); setSelected(null); setSection('today'); setRevealed(false); setPickedChoice(null); setNotice('Session saved for offline review.');
    });
  }

  async function rate(rating: Rating) {
    await run(async () => {
      if (!user || !session) return;
      const card = session.cards[session.index];
      const next = { ...session, index: session.index + 1 };
      const id = crypto.randomUUID();
      await queueReview({ key: id, userId: user.id, kind: 'review', data: {
        id, card_id: card.id, session_id: session.id, rating, version: card.state.version, reviewed_at: new Date().toISOString(),
      } }, next, next.index === next.cards.length ? {
        key: `complete:${session.id}`, userId: user.id, kind: 'complete', sessionId: session.id,
      } : undefined);
      setSession(next); setRevealed(false); setPickedChoice(null); setPending((await jobsFor(user.id)).length);
      if (navigator.onLine) void synchronize();
    });
  }

  async function saveDeck(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      const editing = deckEditor !== 'new' && deckEditor;
      const deck = await api<Deck>(`/flashcards/decks${editing ? `/${editing.id}` : ''}`, {
        method: editing ? 'PUT' : 'POST', body: JSON.stringify({ name: form.get('name'), description: form.get('description'), subject: form.get('subject') }),
      });
      if (selected?.id === deck.id) setSelected(deck);
      setDeckEditor(null); await loadDashboard();
    });
  }

  async function saveCard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await run(async () => {
      if (!selected) return;
      const editing = cardEditor !== 'new' && cardEditor;
      await api(`/flashcards/${editing ? `cards/${editing.id}` : `decks/${selected.id}/cards`}`, {
        method: editing ? 'PUT' : 'POST', body: JSON.stringify({ front: form.get('front'), back: form.get('back'),
          tags: String(form.get('tags') || '').split(',').map(value => value.trim()).filter(Boolean),
          choices: String(form.get('choices') || '').split('\n').map(value => value.trim()).filter(Boolean) }),
      });
      setCards(await api<Card[]>(`/flashcards/decks/${selected.id}/cards`));
      setCardEditor(null); await loadDashboard();
    });
  }

  async function attach(files: FileList | File[], side: 'front' | 'back') {
    await run(async () => {
      if (!cardEditor || cardEditor === 'new') return;
      for (const file of Array.from(files)) {
        const form = new FormData(); form.append('file', file);
        await api(`/flashcards/cards/${cardEditor.id}/images?side=${side}`, { method: 'POST', body: form });
      }
      const updated = await api<Card>(`/flashcards/cards/${cardEditor.id}`);
      setCardEditor(updated); setCards(old => old.map(c => c.id === updated.id ? updated : c));
    });
  }

  const currentCard = session?.cards[session.index];
  const reviewChoices = currentCard ? Array.from(new Set(currentCard.choices?.length ? currentCard.choices :
    [currentCard.back, ...(session?.cards.filter(card => card.id !== currentCard.id).map(card => card.back) || [])].slice(0,4)))
    .sort((a,b) => { const hash=(value:string) => Array.from(currentCard.id+value).reduce((sum,char)=>(sum*31+char.charCodeAt(0))>>>0,0); return hash(a)-hash(b); }) : [];
  const due = decks.reduce((sum, deck) => sum + deck.due_count, 0);
  const subjectGroups = groupBySubject(decks);
  if (!user && restoring) return <main className="auth-form" role="status">Restoring your session…</main>;
  if (!user) return <Auth onUser={signedIn} />;

  return <div className="app-layout"><aside className="sidebar"><a className="brand" href="/"><img src="/anti-rot-logo.jpg" className="brand-logo" alt="" /><span>Anti-Rot</span></a>
    <span className="nav-label">YOUR SPACE</span><button className={!selected && section === 'today' ? 'nav-item active' : 'nav-item'} onClick={() => { setSection('today'); setSelected(null); setSearch(''); }}>☀ <span>Today</span><span className="nav-count">{due}</span></button>
    <button className={selected && !exerciseOpen && !newsOpen ? 'nav-item active' : 'nav-item'} onClick={() => { setSection('today'); setSelected(null); setSearch(''); document.getElementById('decks')?.scrollIntoView({ behavior: 'smooth' }); }}>▤ <span>My decks</span></button>
    <button className={exerciseOpen ? 'nav-item active' : 'nav-item'} onClick={() => { setSection('exercise'); setSelected(null); }}>↗ <span>Exercise</span></button>
    <button className={newsOpen ? 'nav-item active' : 'nav-item'} onClick={() => { setSection('news'); setSelected(null); }}>▧ <span>News</span></button>
    <button aria-label="Activity history" className={historyOpen ? 'nav-item active' : 'nav-item'} onClick={() => { setSection('history'); setSelected(null); }}>▦ <span>Activity history</span></button>
    <div className="sidebar-decks"><span className="nav-label">YOUR SUBJECTS</span>{subjectGroups.map(group => <div className="sidebar-subject" key={group.subject}>
      <h3>{group.subject}</h3>{group.decks.map(deck =>
      <button key={deck.id} className={`sidebar-deck ${selected?.id === deck.id ? 'active' : ''}`} disabled={!online || busy} onClick={() => void openDeck(deck)}>
        <span aria-hidden="true">▤</span><strong>{deck.name}</strong><small>{deck.card_count}</small>
      </button>)}</div>)}{!decks.length && <p className="nav-label">Your decks will appear here.</p>}</div>
    <div className="sidebar-note"><span>↗</span><p>Small steps.<br /><strong>Lasting progress.</strong></p><small>A few minutes today go a long way.</small></div>
    <div className="account"><span className="avatar">{user.email[0].toUpperCase()}</span><div><strong title={user.email}>{user.email.split('@')[0]}</strong><small>Personal workspace</small></div><button className="icon-button" onClick={signOut} aria-label="Sign out" title="Sign out" disabled={busy || !online}>↪</button></div>
  </aside>
  <div className="workspace"><header className="topbar"><span>My workspace <span className="slash">/</span> <strong>{historyOpen ? 'Activity history' : newsOpen ? 'News' : exerciseOpen ? 'Exercise' : selected ? selected.name : 'Today'}</strong></span>
    <button className={`connection ${!online ? 'offline' : ''}`} onClick={() => void synchronize()} title="Sync saved reviews"><i />{online ? pending ? `${pending} pending · Sync` : 'All changes synced' : `Offline${pending ? ` · ${pending} pending` : ''}`}</button></header>
  <main className="content">
    {error && <div className="banner error" role="alert">{error}<button onClick={() => setError('')} aria-label="Dismiss error">×</button>
      {error.startsWith('Sync paused:') && <button className="text-button" onClick={() => void run(async () => {
        if (!confirm('Discard all pending reviews on this device? They will not affect your schedule or streak.')) return;
        await clearPrivateData(); setSession(null); setPending(0); await loadDashboard();
      })}>Discard pending reviews</button>}</div>}
    {notice && <div className="banner" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss message">×</button></div>}

    {historyOpen ? <><button className="text-button back-link" onClick={() => setSection('today')}>← Back to Today</button><HistoryPage /></> : newsOpen ? <><button className="text-button back-link" onClick={() => setSection('today')}>← Back to Today</button><NewsPage /></> : exerciseOpen ? <><button className="text-button back-link" onClick={() => setSection('today')}>← Back to Today</button><ExercisePage onChange={loadDashboard} /></> : session && !selected ? <section className="review-area"><div className="section-heading"><div><span className="eyebrow">A LITTLE FOCUS TIME</span><h1>One card at a time.</h1></div><button className="secondary" disabled={busy} onClick={() => void run(async () => {
      if (currentCard && !confirm('Leave this session? Unrated cards will stay due.')) return;
      await saveData(user.id, 'session', null); setSession(null); setRevealed(false); await loadDashboard();
    })}>Back to Today</button></div>
      {currentCard ? <><div className="review-meta"><span>QUICK SESSION</span><span>{session.index + 1} / {session.cards.length} cards</span></div>
        {!revealed && <label className="review-mode">Review mode<select value={reviewMode} onChange={event => setReviewMode(event.target.value as 'recall'|'choice')}><option value="recall">Recall</option><option value="choice">Multiple choice</option></select></label>}
        <progress value={session.index} max={session.cards.length} aria-label="Session progress" />
        <article className="review-card"><span className="eyebrow">QUESTION</span><p>{currentCard.front}</p><CardImages user={user.id} card={currentCard} side="front" />
          {revealed && <div className="answer"><p>{currentCard.back}</p><CardImages user={user.id} card={currentCard} side="back" /></div>}</article>
        {!revealed ? reviewMode === 'choice' && reviewChoices.length >= 2 ? <div className="answer-choices">{reviewChoices.map(option => <button className="secondary" key={option} onClick={() => { setPickedChoice(option); setRevealed(true); }}>{option}</button>)}</div> : <button className="primary reveal" onClick={() => setRevealed(true)}>Reveal answer <span>↵</span></button> :
          <div className="rating-bar"><p>How well did you know this?</p><div>{(['again', 'hard', 'good', 'easy'] as Rating[]).map((rating, index) =>
            <button key={rating} disabled={busy} className={`rating ${rating}`} onClick={() => void rate(rating)}><span className="rating-number" aria-hidden="true">{index + 1}</span>{rating[0].toUpperCase() + rating.slice(1)}</button>)}</div></div>}
        {pickedChoice !== null && revealed && <p className="review-footnote">{pickedChoice.trim() === currentCard.back.trim() ? 'Correct.' : 'Not quite — check the answer above.'}</p>}
        <p className="review-footnote">FSRS spaced repetition · ✓ Saved on this device for offline review.</p></> :
        <div className="session-done"><div className="done-icon">✓</div><span className="eyebrow">A SMALL WIN, WELL EARNED</span><h2>That’s a session in the books.</h2><p>{session.cards.length} cards reviewed. A little more knowledge, a little more yours.</p><p className="muted">{pending ? 'Your reviews will sync when connected. Your streak updates after sync.' : 'Your reviews and session are saved.'}</p>
          <button className="primary" onClick={() => void run(async () => { await saveData(user.id, 'session', null); setSession(null); await loadDashboard(); })}>Back to my day →</button></div>}
    </section> : selected ? <>
      <button className="text-button back-link" onClick={() => setSelected(null)}>← All decks</button><div className="page-heading"><div><span className="eyebrow">{selected.subject || 'Uncategorized'}</span><h1>{selected.name}</h1><p>{selected.description || 'A growing collection of things worth remembering.'}</p></div><button className="primary" disabled={busy || !online} onClick={() => void start(selected)}>Start quick session →</button></div>
      <div className="deck-toolbar"><input aria-label="Search cards" placeholder="Search this deck…" value={search} onChange={e => setSearch(e.target.value)} />
        <select aria-label="Filter by tag or topic" value={tagFilter} onChange={event => setTagFilter(event.target.value)}><option value="">All tags / topics</option>{Array.from(new Set(cards.flatMap(card => card.tags || []))).sort().map(tag => <option key={tag} value={tag}>{tag}</option>)}</select>
        <label className="secondary file-button">Import CSV<input type="file" accept=".csv,text/csv" disabled={!online || busy} onChange={e => {
          const file = e.target.files?.[0]; e.target.value = '';
          if (file) void run(async () => { const form = new FormData(); form.append('file', file);
            const result = await api<{ imported: number; skipped: number; errors: string[] }>(`/flashcards/decks/${selected.id}/import`, { method: 'POST', body: form });
            setNotice(`Imported ${result.imported}; skipped ${result.skipped}. ${result.errors.join(' ')}`);
            setCards(await api<Card[]>(`/flashcards/decks/${selected.id}/cards`)); await loadDashboard(); });
        }} /></label><button className="primary" disabled={!online || busy} onClick={() => setCardEditor('new')}>+ Add card</button><button className="secondary" disabled={!online || busy} onClick={() => setDeckEditor(selected)}>Edit deck</button></div>
      <p className="muted small">CSV uses UTF-8 front,back columns. Showing up to 1,000 cards.</p>
      <DraftGenerator deckId={selected.id} onSaved={async () => { setCards(await api<Card[]>(`/flashcards/decks/${selected.id}/cards`)); await loadDashboard(); }} />
      <div className="cards-list">{cards.filter(card => (!tagFilter || card.tags?.includes(tagFilter)) && `${card.front} ${card.back} ${(card.tags || []).join(' ')}`.toLowerCase().includes(search.toLowerCase())).map(card => <article className="card-row" key={card.id}>
        <div><span className="eyebrow">FRONT</span><p>{card.front || 'Image card'}</p><div className="card-tags">{card.tags?.map(tag => <span className="badge" key={tag}>{tag}</span>)}</div></div><div><span className="eyebrow">BACK</span><p>{card.back || 'Image card'}</p></div>
        <div className="card-row-actions"><small className="muted">{card.images.length ? `${card.images.length} images · ` : ''}{card.state.interval_days ? `${intervalLabel(card.state.interval_days)} interval` : 'New card'}</small><button className="secondary" disabled={busy || !online} onClick={() => setCardEditor(card)}>Edit</button></div>
      </article>)}{!cards.length && <div className="empty-state"><span>▤</span><h3>Your first card is a good start.</h3><p>Add a question and answer, or bring a collection in with CSV.</p></div>}</div>
      <button className="text-button danger delete-deck" disabled={busy || !online} onClick={() => void run(async () => {
        if (!confirm(`Delete “${selected.name}” and all its cards?`)) return;
        await api(`/flashcards/decks/${selected.id}`, { method: 'DELETE' }); setSelected(null); await loadDashboard();
      })}>Delete this deck</button>
    </> : <>
      <div className="page-heading"><div><span className="eyebrow">{new Intl.DateTimeFormat('en', { weekday: 'long', month: 'long', day: 'numeric' }).format(new Date()).toUpperCase()}</span><h1>A little learning, every day<span className="green">.</span></h1><p>Pick up a deck. Give your future self something to remember.</p></div><span className="sun-symbol" aria-hidden="true">☀</span></div>
      <div className="study-summary"><div><strong>Build knowledge that stays with you.</strong><p>{decks.some(deck => readyCount(deck) > 0) ? 'Your decks, your progress. Start with a focused round of 10 cards.' : due ? 'You’re up to date. Learning cards will return when their next step is due.' : 'Add cards to your decks and start a focused study session.'}</p></div>
        <button className="primary" disabled={!online || busy || !decks.some(deck => readyCount(deck) > 0)} onClick={() => {
          const next = decks.find(deck => readyCount(deck) > 0); if (next) void start(next);
        }}>Study now →</button></div>
      <div className="stats"><article><div className="stat-icon peach">↻</div><div><span>Ready to revisit</span><strong>{due}<small>cards due today</small></strong></div></article>
        <article><div className="stat-icon yellow">♨</div><div><span>Keep the rhythm</span><strong>{today.streak}<small>day streak</small></strong></div></article>
        <article><div className="stat-icon mint">✓</div><div><span>Today’s small wins</span><strong>{today.activities.reduce((s, a) => s + a.completions, 0)}<small>activities completed</small></strong></div></article></div>
      <Today today={today} />
      <section id="decks"><div className="section-heading"><div className="inline-heading"><h2>My decks</h2><span className="count">{decks.length}</span></div><button className="secondary" disabled={!online || busy} onClick={() => setDeckEditor('new')}>+ New deck</button></div>
        {loading ? <p className="muted">Opening your workspace…</p> : <div className="deck-grid">{subjectGroups.map(group => <section className="subject-group" key={group.subject} aria-label={`${group.subject} decks`}>
          <div className="subject-heading"><h3>{group.subject}</h3><span>{group.decks.length} {group.decks.length === 1 ? 'deck' : 'decks'}</span></div>
          {group.decks.map((deck, i) => <article className="deck-tile" key={deck.id}>
          <div className="deck-tile-top"><span className={`deck-icon tone-${i % 3}`}>▤</span><span className={deck.due_count ? 'badge' : 'badge neutral'}>{deck.due_count ? `${deck.due_count} due today` : 'All caught up'}</span></div>
          <button className="deck-title" disabled={!online || busy} onClick={() => void openDeck(deck)}>{deck.name}</button><p>{deck.description || 'A little collection of things worth knowing.'}</p>
          <div className="deck-tile-bottom"><small>{deck.card_count} {deck.card_count === 1 ? 'card' : 'cards'}</small><button className="text-button" disabled={!online || busy || !readyCount(deck)} onClick={() => void start(deck)}>Review deck <span>↗</span></button></div>
        </article>)}</section>)}<button className="new-deck-tile" disabled={!online || busy} onClick={() => setDeckEditor('new')}><span>+</span><strong>{decks.length ? 'Make room for more' : 'Create your first deck'}</strong><small>A new topic. A new possibility.</small></button></div>}
      </section><footer className="page-footer"><span>✦</span> Consistency beats intensity. A few cards is enough for today.</footer>
    </>}
  </main></div>

  {deckEditor && <Modal title={deckEditor === 'new' ? 'A new collection' : 'Edit deck'} close={closeDeck}><form onSubmit={saveDeck}><label>Deck name<input name="name" autoFocus required maxLength={200} defaultValue={deckEditor === 'new' ? '' : deckEditor.name} placeholder="e.g. Week 1: Cell structure" /></label>
    <SubjectSelect initial={deckEditor === 'new' ? '' : deckEditor.subject || ''} disabled={busy} />
    <label>Description<textarea name="description" maxLength={10000} defaultValue={deckEditor === 'new' ? '' : deckEditor.description} placeholder="What are you making room for?" /></label><button className="primary" disabled={busy}>Save deck →</button></form></Modal>}
  {cardEditor && <Modal title={cardEditor === 'new' ? 'Add a little knowledge' : 'Edit card'} close={closeCard}>
    <form onSubmit={saveCard}>{(['front', 'back'] as const).map(side => <div className="card-editor-side" key={side} onPaste={event => {
      const images = Array.from(event.clipboardData.files).filter(f => f.type.startsWith('image/'));
      if (images.length && cardEditor !== 'new') { event.preventDefault(); void attach(images, side); }
    }}><label>{side === 'front' ? 'Front · the prompt' : 'Back · the answer'}<textarea name={side} maxLength={20000} required={cardEditor === 'new'} defaultValue={cardEditor === 'new' ? '' : cardEditor[side]} /></label>
      {cardEditor !== 'new' ? <><CardImages user={user.id} card={cardEditor} side={side} /><div className="attachment-actions">
        <label className="secondary file-button">+ Image<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple disabled={busy} onChange={e => { if (e.target.files) void attach(e.target.files, side); e.target.value = ''; }} /></label>
        <label className="secondary file-button">Camera<input type="file" accept="image/*" capture="environment" disabled={busy} onChange={e => { if (e.target.files) void attach(e.target.files, side); e.target.value = ''; }} /></label>
        {cardEditor.images.filter(image => image.side === side).map((image, i) => <button type="button" className="text-button danger" key={image.id} disabled={busy} onClick={() => void run(async () => {
          await api(`/flashcards/cards/${cardEditor.id}/images/${image.id}`, { method: 'DELETE' });
          const updated = await api<Card>(`/flashcards/cards/${cardEditor.id}`); setCardEditor(updated); setCards(old => old.map(c => c.id === updated.id ? updated : c));
        })}>Remove image {i + 1}</button>)}<small className="muted">Or paste an image into this side.</small></div></> : <small className="muted">Save the card first to attach or paste images.</small>}
    </div>)}<label>Tags / topics<input name="tags" defaultValue={cardEditor === 'new' ? '' : cardEditor.tags?.join(', ') || ''} placeholder="e.g. routing, week-1" /></label>
    <label>Multiple-choice answers<textarea name="choices" defaultValue={cardEditor === 'new' ? '' : cardEditor.choices?.join('\n') || ''} placeholder="Optional: 2–6 options, one per line, including the exact back answer." /></label>
    <div className="modal-actions"><button className="primary" disabled={busy}>Save card →</button>{cardEditor !== 'new' && <button type="button" className="text-button danger" disabled={busy} onClick={() => void run(async () => {
      if (!confirm('Delete this card and its images?')) return;
      await api(`/flashcards/cards/${cardEditor.id}`, { method: 'DELETE' }); setCards(old => old.filter(c => c.id !== cardEditor.id)); setCardEditor(null); await loadDashboard();
    })}>Delete card</button>}</div></form>
    {error && <p className="banner error" role="alert">{error}</p>}
  </Modal>}
  {reauth && <Modal title="Reconnect your account" close={closeReauth}>
    <p className="muted">Sign in as {user.email} to sync. Your saved reviews will stay on this device.</p>
    <form onSubmit={event => {
      event.preventDefault(); const form = new FormData(event.currentTarget);
      void run(async () => {
        const next = await authenticate(user.email, String(form.get('password')));
        signedIn(next); setReauth(false);
      });
    }}><label>Password<input type="password" name="password" autoComplete="current-password" minLength={10} required autoFocus /></label>
      <button className="primary" disabled={busy}>Reconnect and sync →</button>
    </form>{error && <p className="banner error" role="alert">{error}</p>}
  </Modal>}
  </div>;
}
