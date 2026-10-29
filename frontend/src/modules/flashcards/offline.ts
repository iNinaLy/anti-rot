import { api, ApiError, raw } from '../core/api';
import { deleteJob, imageKey, jobsFor, saveImage } from '../core/storage';
import type { ReviewSession } from '../../types';

export async function cacheSessionImages(user: string, session: ReviewSession) {
  for (const card of session.cards) for (const image of card.images) {
    const response = await raw(`/flashcards/cards/${card.id}/images/${image.id}`);
    await saveImage(imageKey(user, card.id, image.id), await response.blob());
  }
}

let syncing: Promise<number> | null = null;
export function syncJobs(user: string): Promise<number> {
  if (syncing) return syncing;
  syncing = (async () => {
    const jobs = await jobsFor(user);
    // All reviews must reach the server before completion records.
    for (const job of jobs.sort((a, b) => Number(a.kind === 'complete') - Number(b.kind === 'complete'))) {
      try {
        if (job.kind === 'review') await api('/flashcards/reviews', { method: 'POST', body: JSON.stringify(job.data) });
        else await api(`/flashcards/sessions/${job.sessionId}/complete`, { method: 'POST' });
        await deleteJob(job.key);
      } catch (error) {
        if (error instanceof ApiError) throw error;
        break; // Connection dropped: retain this and every later operation.
      }
    }
    return (await jobsFor(user)).length;
  })().finally(() => { syncing = null; });
  return syncing;
}
