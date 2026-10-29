export async function compressImage(file: File): Promise<File> {
  let bitmap: ImageBitmap;
  try { bitmap = await createImageBitmap(file); }
  catch { throw new Error('Could not read this image. Use JPEG, PNG, WebP or GIF.'); }
  try {
    const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Image processing is unavailable in this browser.');
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('Could not compress image.')), 'image/webp', 0.8));
    if (blob.size > 5 * 1024 * 1024) throw new Error('This image is still too large. Try cropping it first.');
    return new File([blob], 'card-image.webp', { type: blob.type });
  } finally { bitmap.close(); }
}
