declare const require: (path: string) => any;

describe("SmileResonanceIcon", () => {
  it("uses an open laugh mouth instead of a thin smile arc", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/action-rail-resonance/SmileResonanceIcon.tsx", "utf8");

    expect(source).toContain("LAUGH_FACE_PATH");
    expect(source).toContain("C8.5 15.75 9.95 17.1 12 17.1");
    expect(source).not.toContain("8.7 13.7c.76 1.34");
  });
});
