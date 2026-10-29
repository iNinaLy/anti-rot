export interface User { id: string; email: string }
export interface Deck { id: string; name: string; description: string; subject?: string; card_count: number; due_count: number; ready_count?: number }
export interface CardImage { id: string; side: 'front' | 'back' }
export interface Card { id: string; deck_id: string; front: string; back: string; tags?: string[]; choices?: string[]; images: CardImage[];
  state: { due_at: string; interval_days: number; version: number } }
export interface ReviewSession { id: string; cards: Card[]; index: number }
export type Rating = 'again' | 'hard' | 'good' | 'easy';
export interface Review { id: string; card_id: string; session_id: string; rating: Rating;
  version: number; reviewed_at: string }
export type Job = { key: string; userId: string } &
  ({ kind: 'review'; data: Review } | { kind: 'complete'; sessionId: string });
export interface Today { streak: number; points: number;
  activities: { type: string; label: string; completions: number; points: number }[] }
