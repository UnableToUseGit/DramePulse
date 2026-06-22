declare const require: (path: string) => any;

describe("App startup overlay", () => {
  it("presents a branded app launch screen instead of engineering diagnostics", () => {
    const fs = require("fs");
    const source = fs.readFileSync("App.tsx", "utf8");

    expect(source).toContain("bootLogo");
    expect(source).toContain("DramePulse");
    expect(source).not.toContain("正在预热首屏播放资产");
    expect(source).not.toContain("首页 Feed、剧场卡片、首集分镜和封面缓存会在进入播放前准备好");
    expect(source).not.toContain("GET /api/feed/home");
    expect(source).not.toContain("bootChecklist");
  });

  it("uses a white launch background with black brand text", () => {
    const fs = require("fs");
    const source = fs.readFileSync("App.tsx", "utf8");

    expect(source).toContain('backgroundColor: "#FFFFFF"');
    expect(source).toContain("color: colors.black");
    expect(source).toMatch(/bootBrandText:\s*{[^}]*fontWeight: "700"/s);
  });

  it("lets fast startup skip waiting for the first video playback ready signal", () => {
    const fs = require("fs");
    const source = fs.readFileSync("App.tsx", "utf8");

    expect(source).toContain("ENABLE_FAST_STARTUP");
    expect(source).toContain("!ENABLE_FAST_STARTUP && loadState === \"ready\" && !hasInitialVideoPlaybackReady");
    expect(source).toContain("skipPreload: ENABLE_FAST_STARTUP");
  });
});
