import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

describe('zero-legacy-hero baseline guards', () => {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const login = fs.readFileSync(path.join(root, 'src/screens/LoginScreen.tsx'), 'utf8');
  const postLoginHomes = [
    fs.readFileSync(path.join(root, 'app/customer/index.tsx'), 'utf8'),
    fs.readFileSync(path.join(root, 'app/owner/index.tsx'), 'utf8'),
    fs.readFileSync(path.join(root, 'app/driver/index.tsx'), 'utf8'),
    fs.readFileSync(path.join(root, 'src/screens/StaffHome.tsx'), 'utf8'),
  ];

  it('keeps Login free of the removed legacy hero system', () => {
    assert.doesNotMatch(login, /HERO_LIGHT|HERO_DARK|heroSource|login-hero-(light|dark)|styles\.hero(Image)?/);
  });

  it('keeps post-login homes free of the removed legacy hero system', () => {
    for (const source of postLoginHomes) {
      assert.doesNotMatch(source, /HomeHero|home-hero-(light|dark)/);
    }
  });

  it('does not keep the removed legacy hero files in the repository', () => {
    const removed = [
      'assets/images/login-hero-light.jpg',
      'assets/images/login-hero-dark.jpg',
      'assets/images/home-hero-light.jpg',
      'assets/images/home-hero-dark.jpg',
      'src/components/HomeHero.tsx',
    ];
    for (const relativePath of removed) {
      assert.equal(fs.existsSync(path.join(root, relativePath)), false, `${relativePath} must stay removed`);
    }
  });
});
