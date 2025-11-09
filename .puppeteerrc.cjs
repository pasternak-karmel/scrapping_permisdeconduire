const { join } = require("path");

module.exports = {
  skipDownload: true,

  cacheDirectory: join(__dirname, ".cache", "puppeteer"),

  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || "/usr/bin/chromium",
};
