const { test } = require('node:test');
const assert = require('node:assert');
const app = require('../src/app');

async function withServer(fn) {
  const server = app.listen(0);
  const { port } = server.address();
  try {
    await fn(`http://127.0.0.1:${port}`);
  } finally {
    server.close();
  }
}

test('GET /health returns ok', async () => {
  await withServer(async (base) => {
    const res = await fetch(`${base}/health`);
    assert.strictEqual(res.status, 200);
    assert.deepStrictEqual(await res.json(), { status: 'ok' });
  });
});

test('GET /api/greet capitalizes the name', async () => {
  await withServer(async (base) => {
    const res = await fetch(`${base}/api/greet?name=somchai`);
    assert.strictEqual(res.status, 200);
    assert.deepStrictEqual(await res.json(), { greeting: 'Hello, Somchai!' });
  });
});
