import { test } from 'node:test';
import assert from 'node:assert';
import { add, multiply } from './app.js';

test('add', () => {
  assert.strictEqual(add(1, 2), 3);
});

test('multiply', () => {
  assert.strictEqual(multiply(2, 3), 6);
});
