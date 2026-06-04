declare const require: (path: string) => any;

describe("VideoStage render safety", () => {
  it("does not record resume initialization from the useVideoPlayer setup callback", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/VideoStage.tsx", "utf8");
    const setupStart = source.indexOf("useVideoPlayer(streamUrl");
    const setupEnd = source.indexOf(");", setupStart);
    const setupSource = source.slice(setupStart, setupEnd);

    expect(setupSource).not.toContain('recordObservation("resume_position_initialized"');
  });
});
