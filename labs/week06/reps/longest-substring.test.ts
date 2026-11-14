import assert from "node:assert/strict";
import { test } from "node:test";
import { lengthOfLongestSubstring } from "./longest-substring.js";

const cases: [s: string, expected: number][] = [
  ["", 0],
  [" ", 1],
  ["a", 1],
  ["bbbbb", 1],
  ["abcabcbb", 3],
  ["pwwkew", 3],
  ["dvdf", 3],
  ["abba", 2],
];
for (const [s, expected] of cases) {
  test(`search(${JSON.stringify(s)}) = ${expected}`, () => {
    assert.equal(lengthOfLongestSubstring(s), expected);
  });
}