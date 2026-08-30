import fs from 'node:fs';
import path from 'node:path';

describe('theme-aware hero rendering guards', () => {
  const root = path.resolve(__dirname, '../../..');
  const login = fs.readFileSync(path.join(root, 'app/login.tsx'), 'utf8');
  const home = fs.readFileSync(path.join(root, 'app/customer/index.tsx'), 'utf8');

  it('switches dedicated light and dark assets on login', () => {
    expect(login).toContain('HERO_LIGHT');
    expect(login).toContain('HERO_DARK');
    expect(login).toContain('colors.isDark ? HERO_DARK : HERO_LIGHT');
    expect(login).toContain('contentFit="contain"');
  });

  it('switches dedicated light and dark assets on customer home', () => {
    expect(home).toContain('HERO_LIGHT');
    expect(home).toContain('HERO_DARK');
    expect(home).toContain('colors.isDark ? HERO_DARK : HERO_LIGHT');
    expect(home).toContain('contentFit="contain"');
  });

  it('does not reintroduce cover cropping for either hero', () => {
    expect(login).not.toMatch(/source=\{heroSource\}[\s\S]{0,120}contentFit="cover"/);
    expect(home).not.toMatch(/source=\{heroSource\}[\s\S]{0,120}contentFit="cover"/);
  });
});
