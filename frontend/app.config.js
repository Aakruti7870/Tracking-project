module.exports = ({ config }) => {
  const googleMapsAndroidKey = (process.env.GOOGLE_MAPS_ANDROID_KEY || "").trim();
  const finalAppIcon = "./assets/images/final-app-icon.jpg";

  const android = {
    ...(config.android || {}),
    adaptiveIcon: {
      ...((config.android && config.android.adaptiveIcon) || {}),
      foregroundImage: finalAppIcon,
      backgroundColor: "#FFFFFF",
    },
  };

  if (googleMapsAndroidKey) {
    android.config = {
      ...(android.config || {}),
      googleMaps: {
        ...((android.config && android.config.googleMaps) || {}),
        apiKey: googleMapsAndroidKey,
      },
    };
  }

  return {
    ...config,
    icon: finalAppIcon,
    android,
    web: {
      ...(config.web || {}),
      favicon: finalAppIcon,
    },
    extra: {
      ...(config.extra || {}),
      googleMapsAndroidConfigured: Boolean(googleMapsAndroidKey),
    },
  };
};
