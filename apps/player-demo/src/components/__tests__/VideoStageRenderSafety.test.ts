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

  it("keeps feed video stage mounted from a single PlayerPage render site", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");
    const renderSiteCount = (source.match(/<VideoStage/g) ?? []).length;

    expect(renderSiteCount).toBe(1);
    expect(source).not.toContain(":preload");
  });

  it("disables iOS Live Text frame analysis controls over the custom player chrome", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/VideoStage.tsx", "utf8");

    expect(source).toContain("allowsVideoFrameAnalysis={false}");
  });

  it("bubbles playback readiness out of VideoStage and PlayerPage", () => {
    const fs = require("fs");
    const videoStageSource = fs.readFileSync("src/components/VideoStage.tsx", "utf8");
    const playerPageSource = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");
    const playerFeedSource = fs.readFileSync("src/components/PlayerFeed.tsx", "utf8");

    expect(videoStageSource).toContain("onPlaybackReady?: () => void");
    expect(videoStageSource).toContain("reduceVideoReadinessState");
    expect(videoStageSource).toContain("onPlaybackReady?.()");
    expect(playerPageSource).toContain("onPlaybackReady={onPlaybackReady}");
    expect(playerFeedSource).toContain("onInitialVideoPlaybackReady");
  });

  it("loads lightweight playback assets in PlayerPage and renders controls from the enhanced video", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");

    expect(source).toContain("loadLightweightPlaybackAssets");
    expect(source).not.toContain("loadPlaybackAssets");
    expect(source).toContain("playbackAssetVideo");
    expect(source).toContain("setPlaybackAssetVideo(assets.video)");
    expect(source).toContain("const displayVideo = playbackAssetVideo?.videoId === video.videoId ? playbackAssetVideo : video");
    expect(source).toContain("storyboard={displayVideo.storyboard}");
  });

  it("keeps the storyboard preview image mounted while controls are mounted", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerControls.tsx", "utf8");

    expect(source).toContain("<StoryboardPreview cell={storyboardCell} isVisible={isDragging && storyboardCell !== undefined}");
    expect(source).not.toContain("{storyboardCell ? <StoryboardPreview");
  });

  it("renders interaction trigger markers only through the playback debug panel gate", () => {
    const fs = require("fs");
    const playerPageSource = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");
    const controlsSource = fs.readFileSync("src/components/PlayerControls.tsx", "utf8");

    expect(playerPageSource).toContain("ENABLE_PLAYBACK_DEBUG_PANEL ? toInteractionDebugMarkers(interactionAssets) : []");
    expect(playerPageSource).toContain("debugInteractionMarkers={debugInteractionMarkers}");
    expect(controlsSource).toContain("debugInteractionMarkers?: InteractionDebugMarker[]");
    expect(controlsSource).toContain("pointerEvents=\"none\"");
    expect(controlsSource).toContain("interactionDebugMarkerEmotion");
    expect(controlsSource).toContain("interactionDebugMarkerInnerVoice");
  });

  it("loads remote danmaku only for the active playing page", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");

    expect(source).toContain("const shouldLoadDanmaku = isActive && playbackState.isStarted");
    expect(source).toContain("useDanmakuFeed(video.danmakuUrl, shouldLoadDanmaku, currentTime)");
  });

  it("does not statically import expo-audio so Expo Go can render text assistant", () => {
    const fs = require("fs");
    const pageSource = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");
    const feedSource = fs.readFileSync("src/components/PlayerFeed.tsx", "utf8");

    expect(pageSource).not.toContain('from "expo-audio"');
    expect(feedSource).not.toContain('from "expo-audio"');
    expect(feedSource).toContain('import("expo-audio")');
  });

  it("transcribes recorded watch assistant audio before submitting a voice command", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerFeed.tsx", "utf8");

    expect(source).toContain("transcribeWatchAssistantAudio");
    expect(source).toContain("requestRecordingPermissionsAsync");
    expect(source).toContain("prepareToRecordAsync");
    expect(source).toContain('handleSubmitWatchAssistant(transcription.text, "voice", transcription)');
    expect(source).toContain("voiceDurationSec={assistantState.voiceDurationSec}");
  });
});
