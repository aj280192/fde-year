import assert from "node:assert/strict";
import { test } from "node:test";
import { searchMatrix } from "./search-2d-matrix.js";

const cases: [nums: number[][], target: number, expected: boolean][] = [
  [[[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 3, true],
  [[[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 13, false],
  [[[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 1, true],
  [[[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 60, true],
  [[[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 10, true],
  [[[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 7, true],
  [[[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 0, false],
  [[[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], 61, false],
  [[[5]], 5, true],
  [[[5]], 4, false],
  [[[1,3,5]], 5, true],
  [[[1],[3],[5]], 3, true],
];
for (const [nums, target, expected] of cases) {
  test(`search(${JSON.stringify(nums)}, ${target}) = ${expected}`, () => {
    assert.equal(searchMatrix(nums, target), expected);
  });
}