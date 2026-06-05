jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons"
}));

import { PLAYBACK_RATES } from "../SpeedSelector";

declare const require: (path: string) => any;

describe("SpeedSelector", () => {
  it("only offers normal speed and 2x speed", () => {
    expect(PLAYBACK_RATES).toEqual([1, 2]);
  });

  it("uses the same translucent black button background as the danmaku entry button", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/SpeedSelector.tsx", "utf8");

    expect(source).toContain("backgroundColor: \"rgba(0,0,0,0.46)\"");
    expect(source).not.toContain("...playerOverlay.strongPanel");
  });
});
