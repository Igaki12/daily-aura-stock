export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length === 0 || b.length === 0 || a.length !== b.length) {
    return 0;
  }

  let dot = 0;
  let normA = 0;
  let normB = 0;

  for (let index = 0; index < a.length; index += 1) {
    const valueA = a[index];
    const valueB = b[index];
    dot += valueA * valueB;
    normA += valueA * valueA;
    normB += valueB * valueB;
  }

  if (normA === 0 || normB === 0) {
    return 0;
  }

  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

export function summarizeVector(values: number[]): {
  length: number;
  min: number;
  max: number;
  mean: number;
  head: number[];
} {
  if (values.length === 0) {
    return { length: 0, min: 0, max: 0, mean: 0, head: [] };
  }

  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  let sum = 0;

  for (const value of values) {
    min = Math.min(min, value);
    max = Math.max(max, value);
    sum += value;
  }

  return {
    length: values.length,
    min,
    max,
    mean: sum / values.length,
    head: values.slice(0, 16),
  };
}
