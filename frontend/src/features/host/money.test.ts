import { expect, it } from 'vitest';
import { audInput, centsFromAud } from './money';
it.each([
  ['55.29', 5529],
  ['0.29', 29],
  ['0', 0],
  ['20.1', 2010],
  ['90071992547409.91', 9007199254740991],
])('parses exact AUD %s', (text, cents) => {
  expect(centsFromAud(text)).toBe(cents);
  expect(centsFromAud(audInput(cents))).toBe(cents);
});
it.each(['-1', '1.001', '1e2', 'NaN', '', '90071992547409.92'])(
  'rejects invalid AUD %s',
  (text) => {
    expect(() => centsFromAud(text)).toThrow();
  },
);
