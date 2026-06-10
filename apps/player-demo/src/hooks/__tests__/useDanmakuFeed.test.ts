import { buildDanmakuFetchUrl } from "../useDanmakuFeed";

describe("useDanmakuFeed helpers", () => {
  it("builds a one-shot danmaku request capped at the backend maximum", () => {
    expect(buildDanmakuFetchUrl("http://api.test/api/videos/v1/danmaku")).toBe(
      "http://api.test/api/videos/v1/danmaku?limit=300"
    );
  });

  it("preserves existing query params when adding the one-shot cap", () => {
    expect(buildDanmakuFetchUrl("http://api.test/api/videos/v1/danmaku?source=demo")).toBe(
      "http://api.test/api/videos/v1/danmaku?source=demo&limit=300"
    );
  });
});
