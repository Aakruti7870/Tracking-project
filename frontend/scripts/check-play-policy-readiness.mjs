#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const frontendRoot = path.resolve(process.cwd());
const repoRoot = path.resolve(frontendRoot, '..');

function read(relativeToRepo) {
  return fs.readFileSync(path.join(repoRoot, relativeToRepo), 'utf8');
}

function fail(message) {
  console.error(`PLAY POLICY GATE FAILED: ${message}`);
  process.exitCode = 1;
}

function expect(condition, message) {
  if (!condition) fail(message);
}

function expectIncludes(content, snippet, message) {
  expect(content.includes(snippet), message);
}

const app = JSON.parse(read('frontend/app.json'));
const expo = app.expo || {};
const android = expo.android || {};
const permissions = new Set(android.permissions || []);
const blocked = new Set(android.blockedPermissions || []);

expect(expo.version === '2.0.21', 'Expo version must be 2.0.21 for vc79.');
expect(android.versionCode === 79, 'Android versionCode must be 79.');
expect(android.package === 'com.trackmyrmc.concreteking', 'Android package identity changed unexpectedly.');

for (const permission of [
  'android.permission.READ_MEDIA_IMAGES',
  'android.permission.READ_MEDIA_VIDEO',
  'android.permission.READ_EXTERNAL_STORAGE',
  'android.permission.WRITE_EXTERNAL_STORAGE',
]) {
  expect(blocked.has(permission), `${permission} must remain blocked.`);
}

for (const permission of ['READ_MEDIA_IMAGES', 'READ_MEDIA_VIDEO', 'READ_EXTERNAL_STORAGE', 'WRITE_EXTERNAL_STORAGE']) {
  expect(!permissions.has(permission) && !permissions.has(`android.permission.${permission}`), `${permission} must not be requested as an app permission.`);
}

expect(permissions.has('ACCESS_BACKGROUND_LOCATION'), 'Background location is expected only for active Driver delivery tracking and must remain policy-gated.');

const tripTracking = read('frontend/src/location/tripTracking.ts');
const tripScreen = read('frontend/app/trip/[id].tsx');
expectIncludes(tripTracking, 'options: { allowBackground?: boolean }', 'Background permission must be gated by an explicit caller option.');
expectIncludes(tripTracking, 'options.allowBackground === true', 'Background permission may run only after app-owned consent.');
expectIncludes(tripScreen, 'This app collects location data to enable live mixer delivery tracking even when the app is closed or not in use.', 'Prominent background-location disclosure text is missing.');
expectIncludes(tripScreen, 'Agree & Continue', 'Background-location disclosure requires affirmative consent.');
expectIncludes(tripScreen, 'Not now', 'Background-location disclosure must offer a decline path.');
expectIncludes(tripScreen, 'assigned plant and the authorized customer tracking view', 'Disclosure must explain who receives active-trip location data.');

function walk(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (/\.(ts|tsx|js|jsx)$/.test(entry.name)) out.push(full);
  }
  return out;
}

const frontendSourceFiles = [
  ...walk(path.join(repoRoot, 'frontend', 'app')),
  ...walk(path.join(repoRoot, 'frontend', 'src')),
];
const bgPermissionCallers = frontendSourceFiles.filter((file) =>
  fs.readFileSync(file, 'utf8').includes('requestBackgroundPermissionsAsync('),
);
expect(bgPermissionCallers.length === 1 && bgPermissionCallers[0].endsWith(path.join('src', 'location', 'tripTracking.ts')), 'Background-location runtime permission must be requested only by tripTracking.ts.');

const pushClient = read('frontend/src/notifications/pushClient.ts');
const pushBridge = read('frontend/src/notifications/PushNotificationBridge.tsx');
const notificationsScreen = read('frontend/app/notifications.tsx');
expectIncludes(pushClient, 'requestPermission = false', 'Push registration must not request notification permission by default.');
expectIncludes(pushClient, 'if (permission.status !== "granted" && requestPermission)', 'Android notification prompt must require explicit caller consent.');
expectIncludes(pushBridge, 'Stay updated on your work', 'App-owned notification disclosure is missing.');
expectIncludes(pushBridge, 'Enable notifications', 'Notification disclosure needs an affirmative action.');
expectIncludes(pushBridge, 'Not now', 'Notification disclosure needs a decline path.');
expectIncludes(notificationsScreen, 'Enable device notifications', 'Users must be able to opt into notifications later.');

const reviewScreen = read('frontend/app/review-access.tsx');
const reviewRouter = read('backend/routers/play_review.py');
const reviewFixture = read('backend/play_review.py');
const login = read('frontend/app/login.tsx');
const config = read('backend/config.py');
for (const role of ['customer', 'plant_owner', 'authority', 'driver']) {
  expectIncludes(reviewScreen, `role: "${role}"`, `Review screen is missing ${role}.`);
  expectIncludes(reviewRouter, role, `Reviewer backend is missing ${role}.`);
}
expectIncludes(login, 'App Review Access', 'Reviewer access must be discoverable from sign-in.');
expectIncludes(reviewRouter, 'PLAY_REVIEW_ACCESS_ENABLED', 'Reviewer access must be deployment-gated.');
expectIncludes(reviewRouter, 'compare_digest', 'Reviewer access code comparison must be constant-time.');
expectIncludes(config, 'PLAY_REVIEW_ACCESS_CODE', 'Reviewer access code must be configured server-side.');
expectIncludes(reviewFixture, 'play_review_fixture', 'Reviewer accounts must use isolated demo fixtures.');
expect(!reviewFixture.includes('PLAY_REVIEW_ACCESS_CODE'), 'Reviewer fixture must never contain the access secret.');

const privacy = read('frontend/app/privacy.tsx');
const deletion = read('frontend/app/account-deletion-public.tsx');
const publicPolicy = read('backend/routers/public_policy.py');
const server = read('backend/server.py');
expectIncludes(privacy, 'even when the app is closed or not in use', 'In-app privacy policy must disclose background location.');
expectIncludes(privacy, 'support@goldetech.com', 'Privacy policy must identify a support/privacy contact.');
expectIncludes(deletion, 'request deletion without signing in', 'In-app public deletion flow must remain available outside an authenticated session.');
expectIncludes(publicPolicy, '@router.get("/privacy"', 'Public privacy web resource is missing.');
expectIncludes(publicPolicy, '@router.get("/delete-account"', 'Public account-deletion web resource is missing.');
expectIncludes(server, 'app.include_router(public_policy.router)', 'Public privacy/deletion router is not registered.');

const pod = read('frontend/app/pod/[id].tsx');
expectIncludes(pod, 'Platform.OS === "ios"', 'Android Gallery must avoid broad media-library permission.');
expectIncludes(pod, 'launchImageLibraryAsync', 'POD Gallery must remain a user-initiated picker flow.');

if (process.exitCode) process.exit(process.exitCode);
console.log('Google Play policy readiness assertions passed for TrackMyRMC v2.0.21 / vc79.');
