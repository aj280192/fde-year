// A discriminated union from my own work: the week 5 retrieval runs.
// Run: npx tsx 06-results.ts    Check: npm run check

type Method =
  | { kind: "keyword"; variant: "all" | "any" | "norm" }
  | { kind: "vector" }
  | { kind: "hybrid"; keyword: "any" | "norm"; rerank: boolean };

interface Run {
  readonly runId: number;
  split: "tuning" | "heldout";
  method: Method;
  chunking: string;
  recallAt5: number;
  mrrAt5: number;
}

function describe(m: Method): string {
  switch (m.kind) {
    case "keyword":
      return `keyword (${m.variant})`; // only the keyword variant has `variant`
    case "vector":
      return "vector";
    case "hybrid":
      return `hybrid (${m.keyword})${m.rerank ? " + reranker" : ""}`;
    default: {
      // Adding a kind to Method without a case above makes this line fail to compile.
      const unreachable: never = m;
      return unreachable;
    }
  }
}

const runs: Run[] = [
  {
    runId: 5,
    split: "tuning",
    method: { kind: "hybrid", keyword: "any", rerank: false },
    chunking: "paragraphs",
    recallAt5: 0.531,
    mrrAt5: 0.468,
  },
  {
    runId: 16,
    split: "tuning",
    method: { kind: "hybrid", keyword: "norm", rerank: false },
    chunking: "headings_split",
    recallAt5: 0.59,
    mrrAt5: 0.539,
  },
  {
    runId: 19,
    split: "tuning",
    method: { kind: "hybrid", keyword: "norm", rerank: true },
    chunking: "headings_split",
    recallAt5: 0.649,
    mrrAt5: 0.65,
  },
];

for (const r of runs) {
  console.log(
    `run ${r.runId}: ${describe(r.method)}, ${r.chunking} · Recall@5 ${r.recallAt5.toFixed(3)} · MRR@5 ${r.mrrAt5.toFixed(3)}`,
  );
}

// The best run by Recall@5. `best` starts undefined, so it must be checked before use.
let best: Run | undefined;
for (const r of runs) {
  if (best === undefined || r.recallAt5 > best.recallAt5) best = r;
}
if (best === undefined) {
  console.log("no runs");
} else {
  console.log(`best: run ${best.runId}, ${describe(best.method)} (Recall@5 ${best.recallAt5.toFixed(3)})`);
}

// The exhaustiveness test: adding `| { kind: "rerank_only" }` to Method gives, at `const unreachable`:
//   TS2322: Type '{ kind: "rerank_only"; }' is not assignable to type 'never'.
// (Tried on 14 Nov, then removed.)
