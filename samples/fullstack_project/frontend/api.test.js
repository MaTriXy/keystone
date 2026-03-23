import { test, before, after } from 'node:test';
import assert from 'node:assert';
import { spawn } from 'node:child_process';

const API_BASE = 'http://localhost:5000/api';
let serverProcess;

before(async () => {
  // Start the Python backend
  serverProcess = spawn('python', ['../backend/server.py'], {
    cwd: import.meta.dirname,
    stdio: 'pipe',
  });

  // Wait for server to be ready
  await new Promise((resolve) => setTimeout(resolve, 2000));
});

after(() => {
  if (serverProcess) {
    serverProcess.kill();
  }
});

test('add via API', async () => {
  const res = await fetch(`${API_BASE}/add/1/2`);
  const data = await res.json();
  assert.strictEqual(data.result, 3);
});

test('multiply via API', async () => {
  const res = await fetch(`${API_BASE}/multiply/2/3`);
  const data = await res.json();
  assert.strictEqual(data.result, 6);
});
