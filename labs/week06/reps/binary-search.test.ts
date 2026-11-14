import assert from "node:assert/strict";
import { test } from "node:test";
import { search } from "./binary-search.js";

const cases: [nums: number[], target: number, expected: number][] = [
  [[], 5, -1],
  [[5], 5, 0],
  [[5], 3, -1],
  [[-1, 0, 3, 5, 9, 12], 9, 4],
  [[-1, 0, 3, 5, 9, 12], 2, -1],
  [[-1, 0, 3, 5, 9, 12], -1, 0],
  [[-1, 0, 3, 5, 9, 12], 12, 5],
  [[-1, 0, 3, 5, 9, 12], -5, -1],
  [[-1, 0, 3, 5, 9, 12], 20, -1],
  [[1,2], 2, 1],
];
for (const [nums, target, expected] of cases) {
  test(`search(${JSON.stringify(nums)}, ${target}) = ${expected}`, () => {
    assert.equal(search(nums, target), expected);
  });
}