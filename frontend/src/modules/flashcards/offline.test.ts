import 'fake-indexeddb/auto';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearPrivateData, database, jobsFor, queueReview, readData } from '../core/storage';
import type { ReviewSession } from '../../types';

vi.mock('../core/api', () => ({
  api: vi.fn(), raw: vi.fn(), ApiError: class ApiError extends Error { constructor(public status: number, message: string) { super(message); } },
}));
import { api, ApiError } from '../core/api';
import { syncJobs } from './offline';

const session: ReviewSession = { id: 'session1', index: 1, cards: [] };
const review = { id: 'r1', card_id: 'c1', session_id: 'session1', rating: 'good' as const,
  version: 0, reviewed_at: '2026-10-29T01:00:00Z' };

beforeEach(async () => { await clearPrivateData(); vi.resetAllMocks(); });

describe('durable offline reviews', () => {
  it('saves progress and the review together and isolates accounts', async () => {
    await queueReview({ key: 'r1', userId: 'alice', kind: 'review', data: review }, session);
    expect(await readData('alice', 'session')).toEqual(session);
    expect(await jobsFor('alice')).toHaveLength(1);
    expect(await jobsFor('bob')).toHaveLength(0);
  });

  it('atomically saves the final review, completion and session progress', async () => {
    await queueReview({ key: 'r1', userId: 'alice', kind: 'review', data: review }, session,
      { key: 'complete:session1', userId: 'alice', kind: 'complete', sessionId: 'session1' });
    expect(await jobsFor('alice')).toHaveLength(2);
    expect(await readData('alice', 'session')).toEqual(session);
  });

  it('submits reviews before completion and removes only acknowledged jobs', async () => {
    await queueReview({ key: 'a-complete', userId: 'alice', kind: 'complete', sessionId: 'session1' }, session);
    await queueReview({ key: 'r1', userId: 'alice', kind: 'review', data: review }, session);
    vi.mocked(api).mockResolvedValue({});
    expect(await syncJobs('alice')).toBe(0);
    expect(vi.mocked(api).mock.calls.map(call => call[0])).toEqual([
      '/flashcards/reviews', '/flashcards/sessions/session1/complete',
    ]);
  });

  it('preserves the queue on network loss and retries the original review id', async () => {
    await queueReview({ key: 'r1', userId: 'alice', kind: 'review', data: review }, session);
    vi.mocked(api).mockRejectedValueOnce(new TypeError('Network error'));
    expect(await syncJobs('alice')).toBe(1);
    vi.mocked(api).mockResolvedValue({ duplicate: true });
    expect(await syncJobs('alice')).toBe(0);
    const body = vi.mocked(api).mock.calls[1][1]?.body;
    expect(JSON.parse(String(body)).id).toBe('r1');
  });

  it('stops on a conflict without silently discarding data', async () => {
    await queueReview({ key: 'r1', userId: 'alice', kind: 'review', data: review }, session);
    vi.mocked(api).mockRejectedValue(new ApiError(409, 'Card changed'));
    await expect(syncJobs('alice')).rejects.toThrow('Card changed');
    expect(await jobsFor('alice')).toHaveLength(1);
  });

  it('clears cached images and pending reviews on sign out', async () => {
    await queueReview({ key: 'r1', userId: 'alice', kind: 'review', data: review }, session);
    await (await database).put('images', new Blob(['private']), 'alice:c1:i1');
    await clearPrivateData();
    expect(await jobsFor('alice')).toHaveLength(0);
    expect(await readData('alice', 'session')).toBeUndefined();
    expect(await (await database).count('images')).toBe(0);
  });
});
