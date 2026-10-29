import { useState, type FormEvent } from 'react';
import { api } from '../core/api';

interface Draft { front: string; back: string; tags: string[]; choices: string[]; selected: boolean }

export function DraftGenerator({ deckId, onSaved }: { deckId: string; onSaved: () => Promise<void> }) {
  const [drafts, setDrafts] = useState<Draft[]>([]), [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(''), [error, setError] = useState('');
  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    setBusy(true); setError(''); setMessage('');
    try {
      const file = form.get('pdf') as File;
      let result: { cards: Omit<Draft, 'selected'>[] };
      if (file?.size) {
        const body = new FormData(); body.append('file', file);
        result = await api(`/flashcards/drafts/pdf?count=${Number(form.get('count'))}`, { method: 'POST', body });
      } else result = await api('/flashcards/drafts', { method: 'POST', body: JSON.stringify({ notes: form.get('notes'), count: Number(form.get('count')) }) });
      setDrafts(result.cards.map(card => ({ ...card, choices: [], selected: true })));
    } catch (error) { setError(error instanceof Error ? error.message : 'Could not generate drafts.'); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setError('');
    try {
      const cards = drafts.filter(draft => draft.selected).map(({ selected, ...card }) => card);
      const result = await api<{ imported: number }>(`/flashcards/decks/${deckId}/drafts/save`, { method: 'POST', body: JSON.stringify({ cards }) });
      setDrafts([]); setMessage(`${result.imported} reviewed drafts saved.`); await onSaved();
    } catch (error) { setError(error instanceof Error ? error.message : 'Could not save drafts.'); }
    finally { setBusy(false); }
  }
  return <details className="draft-generator"><summary>Generate flashcard drafts from notes or PDF</summary>
    <p className="muted small">Uses optional local AI. Review and edit every answer before saving.</p>
    <form onSubmit={generate}><label>Source notes<textarea name="notes" minLength={20} maxLength={16000} placeholder="Paste source notes, or upload a text PDF below." /></label>
      <div className="exercise-settings-row"><label>Text PDF<input name="pdf" type="file" accept="application/pdf,.pdf" /></label>
        <label>Number of drafts<select name="count" defaultValue={10}>{[5,10,15,20].map(count => <option key={count} value={count}>{count}</option>)}</select></label></div>
      <button className="secondary" disabled={busy}>{busy ? 'Working…' : 'Generate drafts'}</button></form>
    {error && <p className="banner error" role="alert">{error}</p>}{message && <p className="banner" role="status">{message}</p>}
    {drafts.length > 0 && <div className="draft-list">{drafts.map((draft, index) => <article key={index} className="draft-item">
      <label className="reminder-toggle"><input type="checkbox" checked={draft.selected} onChange={e => setDrafts(old => old.map((value,i) => i===index ? { ...value, selected:e.target.checked } : value))} />Keep draft {index+1}</label>
      <label>Question<textarea value={draft.front} onChange={e => setDrafts(old => old.map((value,i) => i===index ? { ...value, front:e.target.value } : value))} /></label>
      <label>Answer<textarea value={draft.back} onChange={e => setDrafts(old => old.map((value,i) => i===index ? { ...value, back:e.target.value } : value))} /></label>
    </article>)}<button className="primary" disabled={busy || !drafts.some(draft => draft.selected)} onClick={() => void save()}>Save reviewed drafts</button></div>}
  </details>;
}
