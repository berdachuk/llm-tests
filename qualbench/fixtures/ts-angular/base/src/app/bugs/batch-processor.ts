/**
 * Processes a list of items one at a time by calling an async
 * `processOne` function for each, collecting all results in the same
 * order as the input. If any item fails, the whole batch should fail
 * (reject) with that error -- partial/incomplete results must never be
 * returned as if the batch succeeded.
 */
export async function processBatch<T, R>(
  items: T[],
  processOne: (item: T) => Promise<R>,
): Promise<R[]> {
  const results: R[] = [];
  for (const item of items) {
    // BUG: fires off processOne(item) but does not await it before
    // moving to the next iteration, and does not await the collected
    // promises before returning either. This means: (1) items are not
    // actually processed sequentially despite the for-loop's appearance,
    // (2) processBatch resolves with an array of unresolved Promise
    // objects instead of their resolved values, and (3) a rejection from
    // any processOne() call becomes an unhandled promise rejection
    // instead of propagating to the caller of processBatch.
    const resultPromise = processOne(item);
    results.push(resultPromise as unknown as R);
  }
  return results;
}
