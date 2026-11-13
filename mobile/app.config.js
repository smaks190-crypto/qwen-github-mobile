// Firebase is optional; no remote backend or Render URL is required.
const fs = require('node:fs');
const path = require('node:path');
module.exports = ({ config }) => ({
  ...config,
  android: {
    ...config.android,
    ...(fs.existsSync(path.join(__dirname, 'google-services.json'))
      ? { googleServicesFile: './google-services.json' } : {}),
  },
});
