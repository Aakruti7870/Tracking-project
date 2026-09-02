import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

describe('hero rendering guards', () => {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const login = fs.readFileSync(path.join(root, 'src/screens/LoginScreen.tsx'), 'utf8');
  const home = fs.readFileSync(path.join(root, 'app/customer/index.tsx'), 'utf8');

  it('switches dedicated light and dark assets on login', () => {
    assert.ok(login.includes('HERO_LIGHT'));
    assert.ok(login.includes('HERO_DARK'));
    assert.ok(login.includes('colors.isDark ? HERO_DARK : HERO_LIGHT'));
    assert.ok(login.includes('contentFit="contain"'));
  });

  it('keeps post-login home screens native and free of legacy hero assets', () => {
    const postLoginHomes = [
      home,
      fs.readFileSync(path.join(root, 'app/owner/index.tsx'), 'utf8'),
      fs.readFileSync(path.join(root, 'app/driver/index.tsx'), 'utf8'),
      fs.readFileSync(path.join(root, 'src/screens/StaffHome.tsx'), 'utf8'),
    ];
    for (const source of postLoginHomes) assert.doesNotMatch(source, /HomeHero|home-hero-(light|dark)/);
  });

  it('does not reintroduce cover cropping for either hero', () => {
    assert.doesNotMatch(login, /source=\{heroSource\}[\s\S]{0,120}contentFit="cover"/);
  });
});
