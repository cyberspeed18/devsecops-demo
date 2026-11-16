// INTENTIONALLY INSECURE - only here so the scanners (Semgrep, SonarQube)
// have something to find. This file is NOT imported by the app.
// Delete it once you have seen the findings.
const { exec } = require('child_process');

const DB_PASSWORD = 'P@ssw0rd-demo-1234'; // hard-coded credential

function runUserCode(input) {
  return eval(input); // code injection
}

function pingHost(host, callback) {
  exec('ping -c 1 ' + host, callback); // command injection
}

module.exports = { runUserCode, pingHost, DB_PASSWORD };
