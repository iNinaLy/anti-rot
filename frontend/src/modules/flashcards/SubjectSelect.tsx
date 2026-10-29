import { useEffect, useRef, useState } from 'react';
import { api } from '../core/api';

const ADD_SUBJECT = '__add_subject__';

export function SubjectSelect({ initial = '', disabled = false }: { initial?: string; disabled?: boolean }) {
  const [subjects, setSubjects] = useState<string[]>(initial ? [initial] : []);
  const [selected, setSelected] = useState(initial);
  const [adding, setAdding] = useState(false), [name, setName] = useState('');
  const [saving, setSaving] = useState(false), [error, setError] = useState('');
  const select = useRef<HTMLSelectElement>(null);
  useEffect(() => {
    select.current?.setCustomValidity(adding ? 'Add the new subject or cancel before saving the deck.' : '');
  }, [adding]);
  useEffect(() => {
    let active = true;
    api<string[]>('/flashcards/subjects').then(items => {
      if (active) setSubjects(previous => [...new Set([...items, ...previous])]);
    }).catch(() => { if (active) setError('Could not load subjects. Close the form and try again.'); });
    return () => { active = false; };
  }, [initial]);

  async function add() {
    if (!name.trim() || saving) return;
    setSaving(true); setError('');
    try {
      const subject = await api<{ name: string }>('/flashcards/subjects', {
        method: 'POST', body: JSON.stringify({ name: name.trim() }),
      });
      setSubjects(items => items.includes(subject.name) ? items : [...items, subject.name]);
      setSelected(subject.name); setAdding(false); setName('');
    } catch (error) { setError(error instanceof Error ? error.message : 'Could not add subject.'); }
    finally { setSaving(false); }
  }

  return <div className="subject-select">
    <label>University subject<select ref={select} name="subject" value={selected} disabled={disabled} onChange={event => {
      if (event.target.value === ADD_SUBJECT) { setAdding(true); setError(''); }
      else { setSelected(event.target.value); setAdding(false); setError(''); }
    }}><option value="">Uncategorized</option>{subjects.map(subject => <option key={subject} value={subject}>{subject}</option>)}
      <option value={ADD_SUBJECT}>+ Add subject…</option>
    </select></label>
    {adding && <div className="add-subject"><label>New subject<input value={name} maxLength={120} disabled={disabled || saving} autoFocus
      placeholder="e.g. ITT700 – Advanced Networking" onChange={event => setName(event.target.value)}
      onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void add(); } }} /></label>
      <div className="attachment-actions"><button type="button" className="secondary" disabled={disabled || saving || !name.trim()} onClick={() => void add()}>{saving ? 'Adding…' : 'Add subject'}</button>
        <button type="button" className="text-button" disabled={saving} onClick={() => { setAdding(false); setName(''); setError(''); }}>Cancel</button></div>
    </div>}
    {error && <p className="error banner" role="alert">{error}</p>}
  </div>;
}
