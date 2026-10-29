import { useEffect, useState } from 'react';

export function PendingImage({ file }: { file: File }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    const next = URL.createObjectURL(file); setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  return <img src={url} className="card-image" alt="Image ready to attach" />;
}
