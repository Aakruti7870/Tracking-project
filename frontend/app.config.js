const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const FINAL_ICON_SHA256 = "5c7025bfde202bf8fd4f2f9af4ae642b0e1dab3dcbec7166910eeede0f57b5d7";
const FINAL_ICON_BYTES = 53192;
const FINAL_ICON_PARTS = 8;

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function materializeFinalIcon() {
  const sourceDir = path.join(__dirname, "assets", "app-icon-source");
  const partNames = fs
    .readdirSync(sourceDir)
    .filter((name) => /^part-\d{2}\.txt$/.test(name))
    .sort();

  if (partNames.length !== FINAL_ICON_PARTS) {
    throw new Error(
      `Final TrackMyRMC icon source is incomplete: expected ${FINAL_ICON_PARTS} parts, found ${partNames.length}`,
    );
  }

  const encoded = partNames
    .map((name) => fs.readFileSync(path.join(sourceDir, name), "utf8").trim())
    .join("");
  const iconBytes = Buffer.from(encoded, "base64");

  if (iconBytes.length !== FINAL_ICON_BYTES || sha256(iconBytes) !== FINAL_ICON_SHA256) {
    throw new Error("Final TrackMyRMC icon failed integrity verification");
  }

  const imageDir = path.join(__dirname, "assets", "images");
  const targets = [
    "icon.png",
    "adaptive-icon.png",
    "favicon.png",
    "ic_launcher_playstore.png",
  ];

  for (const fileName of targets) {
    const target = path.join(imageDir, fileName);
    const current = fs.existsSync(target) ? fs.readFileSync(target) : null;
    if (!current || sha256(current) !== FINAL_ICON_SHA256) {
      fs.writeFileSync(target, iconBytes);
    }
  }
}

module.exports = ({ config }) => {
  materializeFinalIcon();

  const googleMapsAndroidKey = (process.env.GOOGLE_MAPS_ANDROID_KEY || "").trim();

  const android = {
    ...(config.android || {}),
    adaptiveIcon: {
      ...((config.android && config.android.adaptiveIcon) || {}),
      foregroundImage: "./assets/images/adaptive-icon.png",
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
    icon: "./assets/images/icon.png",
    android,
    web: {
      ...(config.web || {}),
      favicon: "./assets/images/favicon.png",
    },
    extra: {
      ...(config.extra || {}),
      googleMapsAndroidConfigured: Boolean(googleMapsAndroidKey),
      finalAppIconSha256: FINAL_ICON_SHA256,
    },
  };
};
