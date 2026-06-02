import { formatResonanceCount, getParticipatingCount } from "../formatCount";

describe("action rail resonance count formatting", () => {
  it("formats large counts as compact Chinese public counts", () => {
    expect(formatResonanceCount(82000)).toBe("8.2万");
    expect(formatResonanceCount(120000)).toBe("12万");
    expect(formatResonanceCount(6626)).toBe("6626");
  });

  it("increments the displayed count once after participation", () => {
    expect(getParticipatingCount({ baseCount: 82000, hasParticipated: false })).toBe(82000);
    expect(getParticipatingCount({ baseCount: 82000, hasParticipated: true })).toBe(82001);
  });
});
