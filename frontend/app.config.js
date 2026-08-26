const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const FINAL_ICON_SHA256 = "5c7025bfde202bf8fd4f2f9af4ae642b0e1dab3dcbec7166910eeede0f57b5d7";
const FINAL_ICON_BYTES = 53192;
const FINAL_ICON_SOURCE_FILES = [
  "part-00.txt",
  "part-01.txt",
  "part-02.txt",
  "part-03.txt",
  "part-04.txt",
  "part-04b.txt",
  "part-05.txt",
  "part-06.txt",
  "part-07.txt",
  "part-07b.txt",
  "part-08.txt",
  "part-09.txt",
];

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function materializeFinalIcon() {
  const sourceDir = path.join(__dirname, "assets", "app-icon-source");
  const encoded = FINAL_ICON_SOURCE_FILES
    .map((name) => {
      const source = path.join(sourceDir, name);
      if (!fs.existsSync(source)) {
        throw new Error(`Final TrackMyRMC icon source is missing: ${name}`);
      }
      return fs.readFileSync(source, "utf8").trim();
    })
    .join("");

  const iconBytes = Buffer.from(encoded, "base64");
  const iconSha256 = sha256(iconBytes);
  if (iconBytes.length !== FINAL_ICON_BYTES || iconSha256 !== FINAL_ICON_SHA256) {
    throw new Error(
      `Final TrackMyRMC icon failed integrity verification: bytes=${iconBytes.length}, sha256=${iconSha256}`,
    );
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
