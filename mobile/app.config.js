// Firebase is optional for local/test APK builds.
// If a client google-services.json is present, Expo includes it during prebuild.
const fs = require('node:fs');
const path = require('node:path');

module.exports = ({ config }) => {
  const googleServices = path.join(__dirname, 'google-services.json');
  return {
    ...config,
    android: {
      ...config.android,
      ...(fs.existsSync(googleServices)
        ? { googleServicesFile: './google-services.json' }
        : {}),
    },
  };
};
