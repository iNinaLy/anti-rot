import { openDB } from 'idb';
import type { Job, ReviewSession } from '../../types';

export const database = openDB('daymark-private-v1', 1, {
  upgrade(db) {
    db.createObjectStore('data');
    db.createObjectStore('images');
    const jobs = db.createObjectStore('jobs', { keyPath: 'key' });
    jobs.createIndex('user', 'userId');
  },
});

export async function saveData<T>(user: string, name: string, value: T) {
  return (await database).put('data', value, `${user}:${name}`);
}
export async function readData<T>(user: string, name: string): Promise<T | undefined> {
  return (await database).get('data', `${user}:${name}`);
}
export const imageKey = (user: string, card: string, image: string) => `${user}:${card}:${image}`;
export async function saveImage(key: string, blob: Blob) { return (await database).put('images', blob, key); }
export async function readImage(key: string): Promise<Blob | undefined> { return (await database).get('images', key); }
export async function jobsFor(user: string): Promise<Job[]> {
  return (await database).getAllFromIndex('jobs', 'user', user);
}
export async function deleteJob(key: string) { return (await database).delete('jobs', key); }

export async function queueReview(job: Job, session: ReviewSession, completion?: Job) {
  const db = await database;
  const tx = db.transaction(['jobs', 'data'], 'readwrite');
  await tx.objectStore('jobs').put(job);
  if (completion) await tx.objectStore('jobs').put(completion);
  await tx.objectStore('data').put(session, `${job.userId}:session`);
  await tx.done;
}

export async function clearPrivateData() {
  const db = await database;
  const tx = db.transaction(['jobs', 'data', 'images'], 'readwrite');
  await Promise.all(['jobs', 'data', 'images'].map(store => tx.objectStore(store).clear()));
  await tx.done;
}
