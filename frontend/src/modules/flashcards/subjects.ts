import type { Deck } from '../../types';

export function groupBySubject(decks: Deck[]): { subject: string; decks: Deck[] }[] {
  const groups = new Map<string, { subject: string; decks: Deck[] }>();
  for (const deck of decks) {
    const subject = deck.subject?.trim() || 'Uncategorized';
    const key = subject.toLocaleLowerCase();
    if (!groups.has(key)) groups.set(key, { subject, decks: [] });
    groups.get(key)!.decks.push(deck);
  }
  return [...groups.values()].sort((a, b) => {
    const aUncategorized = a.subject.toLocaleLowerCase() === 'uncategorized';
    const bUncategorized = b.subject.toLocaleLowerCase() === 'uncategorized';
    return Number(aUncategorized) - Number(bUncategorized) || a.subject.localeCompare(b.subject);
  });
}
