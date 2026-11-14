export function lengthOfLongestSubstring(s: string): number{
    let charSet = new Set<string>();
    let l = 0;
    let result = 0;
    for (let r = 0; r < s.length; r++) {
        while (charSet.has(s[r])){
            charSet.delete(s[l]);
            l += 1;
        }
        charSet.add(s[r]);
        result = Math.max(result, r - l + 1);
    }
    return result;
}