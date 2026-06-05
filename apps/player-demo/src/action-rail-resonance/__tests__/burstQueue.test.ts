import { appendBurstToQueue } from "../burstQueue";

describe("action rail resonance burst queue", () => {
  it("keeps a fast tap run visible instead of clipping after four bursts", () => {
    const bursts = Array.from({ length: 10 }, (_, index) => ({ id: index + 1 })).reduce(
      (queue, burst) => appendBurstToQueue(queue, burst),
      [] as { id: number }[]
    );

    expect(bursts.map((burst) => burst.id)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  });
});
