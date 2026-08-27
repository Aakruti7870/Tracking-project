const { withAndroidManifest } = require('@expo/config-plugins');

const BLOCKED_MEDIA_PERMISSIONS = new Set([
  'android.permission.READ_MEDIA_IMAGES',
  'android.permission.READ_MEDIA_VIDEO',
  'android.permission.READ_EXTERNAL_STORAGE',
]);

const OPTIONAL_HARDWARE_FEATURES = [
  'android.hardware.camera',
  'android.hardware.camera.autofocus',
  'android.hardware.location',
  'android.hardware.location.gps',
  'android.hardware.location.network',
];

module.exports = function withPlayStoreCompatibility(config) {
  return withAndroidManifest(config, (modConfig) => {
    const manifest = modConfig.modResults.manifest;

    const permissions = Array.isArray(manifest['uses-permission'])
      ? manifest['uses-permission']
      : [];
    manifest['uses-permission'] = permissions.filter((entry) => {
      const name = entry && entry.$ && entry.$['android:name'];
      return !BLOCKED_MEDIA_PERMISSIONS.has(name);
    });

    const features = Array.isArray(manifest['uses-feature'])
      ? manifest['uses-feature']
      : [];

    for (const name of OPTIONAL_HARDWARE_FEATURES) {
      const existing = features.find(
        (entry) => entry && entry.$ && entry.$['android:name'] === name,
      );

      if (existing) {
        existing.$['android:required'] = 'false';
      } else {
        features.push({
          $: {
            'android:name': name,
            'android:required': 'false',
          },
        });
      }
    }

    manifest['uses-feature'] = features;
    return modConfig;
  });
};
