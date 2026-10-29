// Size the supplied logo for installable PWA and Apple touch icons without cropping.
// Run after installing frontend dependencies and Playwright Chromium.
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('@playwright/test');
const publicDir = new URL('../frontend/public/', import.meta.url);
const logo = (await readFile(new URL('anti-rot-logo.jpg', publicDir))).toString('base64');
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  for (const size of [192, 512]) {
    const data = await page.evaluate(async ({ logo, size }) => {
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = size;
      const context = canvas.getContext('2d');
      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, size, size);
      const image = new Image();
      image.src = 'data:image/jpeg;base64,' + logo;
      await image.decode();
      const scale = size * 0.8 / Math.max(image.naturalWidth, image.naturalHeight);
      const width = image.naturalWidth * scale;
      const height = image.naturalHeight * scale;
      context.drawImage(image, (size - width) / 2, (size - height) / 2, width, height);
      return canvas.toDataURL('image/png').split(',')[1];
    }, { logo, size });
    await writeFile(new URL(`icon-${size}.png`, publicDir), Buffer.from(data, 'base64'));
  }
} finally {
  await browser.close();
}
