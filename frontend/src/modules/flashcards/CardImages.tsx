import { useEffect, useState } from 'react';
import { raw } from '../core/api';
import { imageKey, readImage, saveImage } from '../core/storage';
import type { Card } from '../../types';

function PrivateImage({ user, card, image }: { user: string; card: string; image: string }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    let active = true, objectUrl = '';
    (async () => {
      const key = imageKey(user, card, image);
      let blob = await readImage(key);
      if (!blob) {
        blob = await (await raw(`/flashcards/cards/${card}/images/${image}`)).blob();
        await saveImage(key, blob);
      }
      if (active) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); }
    })().catch(() => {});
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [user, card, image]);
  return url ? <img className="card-image" src={url} alt="Card attachment" /> : <span className="muted">Image unavailable offline</span>;
}

export function CardImages({ user, card, side }: { user: string; card: Card; side: 'front' | 'back' }) {
  return <div className="card-images">{card.images.filter(image => image.side === side).map(image =>
    <PrivateImage key={image.id} user={user} card={card.id} image={image.id} />)}</div>;
}
