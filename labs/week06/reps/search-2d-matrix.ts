export function searchMatrix(matrix: readonly (readonly number[])[], target: number): boolean {
    if (matrix.length === 0 || matrix[0].length === 0) {
        return false;
    }
    const rows = matrix.length;
    const cols = matrix[0].length;

    let low = 0;
    let high = rows * cols - 1;

    while (low <= high) {
        const mid = Math.floor((low + high) / 2 );

        const row = Math.floor(mid / cols);
        const col = mid % cols;
        const midValue = matrix[row][col];

        if (target === midValue) {
            return true;
        } else if (target > midValue) {
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }

    return false;

}