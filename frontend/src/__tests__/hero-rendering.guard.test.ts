import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

describe('theme-aware hero rendering guards', () => {
  const root = path.resolve(__dirname, '../../..');
  const login = fs.readFileSync(path.join(root, 'app/login.tsx'), 'utf8');
  const home = fs.readFileSync(path.join(root, 'app/customer/index.tsx'), 'utf8');

  it('switches dedicated light and dark assets on login', () => {
    assert.ok(login.includes('HERO_LIGHT'));
    assert.ok(login.includes('HERO_DARK'));
    assert.ok(login.includes('colors.isDark ? HERO_DARK : HERO_LIGHT'));
    assert.ok(login.includes('contentFit="contain"'));
  });

  it('switches dedicated light and dark assets on customer home', () => {
    assert.ok(home.includes('HERO_LIGHT'));
    assert.ok(home.includes('HERO_DARK'));
    assert.ok(home.includes('colors.isDark ? HERO_DARK : HERO_LIGHT'));
    assert.ok(home.includes('contentFit="contain"'));
  });

  it('does not reintroduce cover cropping for either hero', () => {
    assert.doesNotMatch(login, /source=\{heroSource\}[\s\S]{0,120}contentFit="cover"/);
    assert.doesNotMatch(home, /source=\{heroSource\}[\s\S]{0,120}contentFit="cover"/);
  });
});
