import fs from 'node:fs';

const app = JSON.parse(fs.readFileSync(new URL('../app.json', import.meta.url), 'utf8'));
const releaseWorkflow = fs.readFileSync(new URL('../../.github/workflows/release-signed-aab.yml', import.meta.url), 'utf8');
const candidateWorkflow = fs.readFileSync(new URL('../../.github/workflows/pre-aab-candidate-validation.yml', import.meta.url), 'utf8');
const deployWorkflow = fs.readFileSync(new URL('../../.github/workflows/deploy-production-web.yml', import.meta.url), 'utf8');
const indexRoute = fs.readFileSync(new URL('../app/index.tsx', import.meta.url), 'utf8');

function requireInvariant(condition, message) {
  if (!condition) throw new Error(message);
}

requireInvariant(app.expo.version === '2.0.28', 'Expected Expo version 2.0.28');
requireInvariant(app.expo.android?.versionCode === 86, 'Expected Android versionCode 86');
requireInvariant(app.expo.android?.package === 'com.trackmyrmc.concreteking', 'Unexpected Android application id');
requireInvariant(indexRoute.includes('<Redirect href="/login"'), 'Root route must start at /login');

requireInvariant(
  releaseWorkflow.includes('EXPO_PUBLIC_BACKEND_URL: https://trackmyrmc.com'),
  'Signed AAB must be pinned to https://trackmyrmc.com',
);
requireInvariant(
  releaseWorkflow.includes("android:versionCode=\"86\"") && releaseWorkflow.includes("android:versionName=\"2.0.28\""),
  'Signed AAB workflow must validate vc86 / v2.0.28',
);
requireInvariant(
  releaseWorkflow.includes("Legacy api.trackmyrmc.com origin detected"),
  'Signed AAB workflow must reject the legacy api.trackmyrmc.com origin',
);
requireInvariant(
  !candidateWorkflow.includes('ref: feat/login-auth-rebuild'),
  'Pre-AAB candidate validation must not check out the legacy login branch',
);
requireInvariant(
  candidateWorkflow.includes('ref: ${{ github.sha }}'),
  'Push candidate validation must use the exact pushed SHA',
);
requireInvariant(
  deployWorkflow.includes('WWW_HOST: www.trackmyrmc.com'),
  'Production web gate must validate the www host',
);
requireInvariant(
  deployWorkflow.includes('Built for every pour|Ready-Mix Concrete Tracking & RMC Plant Discovery'),
  'Production web gate must reject legacy landing content',
);

console.log('Fresh production release invariants: PASS');
