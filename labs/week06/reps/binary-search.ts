export function search(nums: readonly number[], target: number): number {
    let low = 0;
    let high = nums.length - 1;

    while (low <= high) {
        const mid = Math.floor((low + high) / 2);

        if (target === nums[mid]) {
            return mid;
        } else if (target > nums[mid]) {
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }

    return -1;
}
