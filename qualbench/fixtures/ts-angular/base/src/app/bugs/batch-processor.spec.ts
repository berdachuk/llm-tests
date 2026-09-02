import { processBatch } from './batch-processor';

describe('processBatch', () => {
  it('resolves with the actual resolved values in input order, not raw promises', async () => {
    const results = await processBatch([1, 2, 3], async (n) => n * 10);
    expect(results).toEqual([10, 20, 30]);
  });

  it('processes items sequentially, not concurrently', async () => {
    const order: number[] = [];
    await processBatch([30, 10, 20], async (delayMs) => {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      order.push(delayMs);
      return delayMs;
    });
    // If processed sequentially in input order, they must complete in
    // that same order (30, then 10, then 20) even though 10 and 20 have
    // shorter individual delays -- sequential processing means the next
    // item doesn't even START until the previous one finishes.
    expect(order).toEqual([30, 10, 20]);
  });

  it('rejects the whole batch when one item fails, instead of resolving with partial results', async () => {
    await expect(
      processBatch([1, 2, 3], async (n) => {
        if (n === 2) {
          throw new Error(`failed on ${n}`);
        }
        return n;
      }),
    ).rejects.toThrow('failed on 2');
  });
});
