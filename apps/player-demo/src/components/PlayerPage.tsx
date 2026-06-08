import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { ActionRailResonanceBurstLayer } from "../action-rail-resonance/ActionRailResonanceBurstLayer";
import { ACTION_RAIL_RESONANCE_CUES } from "../action-rail-resonance/cues";
import {
  getActiveActionRailResonanceCue,
  getVisibleActionRailResonanceCue,
  shouldResetActionRailResonanceCue
} from "../action-rail-resonance/scheduler";
import {
  createInitialResonanceTapState,
  ResonanceTapState
} from "../action-rail-resonance/tapState";
import type { ActionRailResonanceCue } from "../action-rail-resonance/types";
import { API_BASE_URL, ENABLE_INTERACTION_LAB } from "../config";
import {
  getFeedPlaybackPagePresentationState,
  getFeedPlaybackPageRenderState,
  type FeedPlaybackPageRole
} from "../domain/feedPlaybackCoordinator";
import {
  getTimelineChromeVisibility,
  getVideoPlaybackState,
  UserPlaybackIntent
} from "../domain/playerFeed";
import type { HomeFeedPlaybackObserver } from "../domain/homeFeedPlaybackObserver";
import type { PlaybackAssetCache } from "../domain/playbackAssetCache";
import { prefetchStoryboardSheets } from "../domain/playbackAssetPreloader";
import { PlayerVideo } from "../domain/playerApi";
import { loadLightweightPlaybackAssets } from "../domain/playerDataApi";
import { askStoryQa, resolveStoryQaContext } from "../domain/storyQa";
import { resetStoryQaState, StoryQaPanelState } from "../domain/storyQaState";
import { FEED_VIDEO_SOURCE_CACHING_ENABLED, getFeedVideoBufferOptions } from "../domain/videoSource";
import { useDanmakuFeed } from "../hooks/useDanmakuFeed";
import { useInteractionExampleState } from "../hooks/useInteractionExampleState";
import { usePlaybackSpeedControls } from "../hooks/usePlaybackSpeedControls";
import { createSentInnerVoiceDanmakuFromCue, toDanmakuItems } from "../inner-voice-danmaku/sentDanmaku";
import type { InnerVoiceDanmakuCue, SentInnerVoiceDanmaku } from "../inner-voice-danmaku/types";
import { DEFAULT_INTERACTION_EXAMPLE } from "../interaction-examples/examples";
import { DanmakuPollExample } from "../interaction-examples/DanmakuPollExample";
import { InteractionLabControls } from "../interaction-examples/InteractionLabControls";
import { isActionRailResonancePresentation, shouldResetExample } from "../interaction-examples/trigger";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { DanmakuLayer } from "./DanmakuLayer";
import { FastForwardPressLayer } from "./FastForwardPressLayer";
import { PlaybackHint } from "./PlaybackHint";
import { PlayerChrome } from "./PlayerChrome";
import { PlayerBottomTabs } from "./PlayerBottomTabs";
import { PlayerControls } from "./PlayerControls";
import { StoryQaPanel } from "./StoryQaPanel";
import { SeekRequest, VideoStage } from "./VideoStage";
import { SeriesEpisodeBar } from "./SeriesEpisodeBar";

const UI_TIME_UPDATE_INTERVAL_SEC = 1;
const ACTION_RAIL_RESONANCE_BUTTON_DISMISS_DELAY_MS = 520;
const ACTION_RAIL_RESONANCE_EFFECT_HOLD_MS = 1500;

function getActionRailPreviewCue(type: InteractionPresentationType) {
  if (type === "action_rail_thrill") {
    return ACTION_RAIL_RESONANCE_CUES.find((cue) => cue.emotionType === "爽点");
  }
  if (type === "action_rail_candy") {
    return ACTION_RAIL_RESONANCE_CUES.find((cue) => cue.emotionType === "甜点");
  }
  if (type === "action_rail_laugh") {
    return ACTION_RAIL_RESONANCE_CUES.find((cue) => cue.emotionType === "笑点");
  }
  if (type === "action_rail_tear") {
    return ACTION_RAIL_RESONANCE_CUES.find((cue) => cue.emotionType === "泪点");
  }
  return undefined;
}

interface PlayerPageProps {
  video: PlayerVideo;
  pageIndex: number;
  playbackAssetCache: PlaybackAssetCache;
  playbackObserver?: HomeFeedPlaybackObserver;
  isActive: boolean;
  pageRole: FeedPlaybackPageRole;
  visualPageRole: FeedPlaybackPageRole;
  height: number;
  videoHeight: number;
  controlsBottomOffset: number;
  metaBottomOffset: number;
  actionRailBottomOffset: number;
  resumePlaybackTime: number;
  hasNextEpisode: boolean;
  nextEpisodeLabel?: string;
  selectedPresentationType: InteractionPresentationType;
  onChangePresentationType: (type: InteractionPresentationType) => void;
  onPlaybackPositionChange: (videoId: string, time: number) => void;
  onTimelineDragStateChange?: (isDragging: boolean) => void;
  onFirstFrameRender?: () => void;
  onPlayNextEpisode: () => void;
  mode?: "home" | "series";
  seriesEpisodeCount?: number;
  onOpenTheater?: () => void;
  onBack?: () => void;
  onOpenSeriesDetail?: () => void;
}

interface VideoStageObservation {
  observer: HomeFeedPlaybackObserver;
  videoId: string;
  pageIndex: number;
}

export function PlayerPage({
  video,
  pageIndex,
  playbackAssetCache,
  playbackObserver,
  isActive,
  pageRole,
  visualPageRole,
  height,
  videoHeight,
  controlsBottomOffset,
  metaBottomOffset,
  actionRailBottomOffset,
  resumePlaybackTime,
  hasNextEpisode,
  nextEpisodeLabel,
  selectedPresentationType,
  onChangePresentationType,
  onPlaybackPositionChange,
  onTimelineDragStateChange,
  onFirstFrameRender,
  onPlayNextEpisode,
  mode = "home",
  seriesEpisodeCount,
  onOpenTheater,
  onBack,
  onOpenSeriesDetail
}: PlayerPageProps) {
  const [currentTime, setCurrentTime] = useState(0);
  const [userPlaybackIntent, setUserPlaybackIntent] = useState<UserPlaybackIntent>("playing");
  const [resolvedDuration, setResolvedDuration] = useState(video.duration);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [seekVersion, setSeekVersion] = useState(0);
  const [liked, setLiked] = useState(false);
  const [isTimelineDragging, setIsTimelineDragging] = useState(false);
  const [sentInnerVoiceDanmaku, setSentInnerVoiceDanmaku] = useState<SentInnerVoiceDanmaku[]>([]);
  const [completedResonanceCueIds, setCompletedResonanceCueIds] = useState<Set<string>>(() => new Set());
  const [participatingResonanceCue, setParticipatingResonanceCue] = useState<ActionRailResonanceCue | undefined>();
  const [resonanceTapState, setResonanceTapState] = useState<ResonanceTapState>(() =>
    createInitialResonanceTapState()
  );
  const [storyQaState, setStoryQaState] = useState<StoryQaPanelState>(() => resetStoryQaState());
  const [playbackAssetVideo, setPlaybackAssetVideo] = useState<PlayerVideo | undefined>(() => {
    const cached = playbackAssetCache.get(video.videoId);
    return cached?.storyboard ? { ...video, storyboard: cached.storyboard } : undefined;
  });
  const previousTimeRef = useRef(0);
  const lastPublishedTimeRef = useRef(0);
  const didCompleteRef = useRef(false);
  const wasActiveRef = useRef(false);
  const previousVideoIdRef = useRef(video.videoId);
  const lastReportedPositionRef = useRef(0);
  const storyQaRequestRef = useRef(0);
  const resonanceButtonDismissTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const resonanceEffectTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const playbackState = getVideoPlaybackState({ isActive, userPlaybackIntent });
  const { danmaku, danmakuState } = useDanmakuFeed(video.danmakuUrl, false);
  const videoRenderState = getFeedPlaybackPageRenderState(pageRole);
  const renderState = getFeedPlaybackPagePresentationState({
    playbackPageRole: pageRole,
    visualPageRole
  });
  const videoBufferOptions = getFeedVideoBufferOptions(pageRole);
  const videoObservation = useMemo(
    () =>
      playbackObserver
        ? {
            observer: playbackObserver,
            videoId: video.videoId,
            pageIndex
          }
        : undefined,
    [pageIndex, playbackObserver, video.videoId]
  );
  const timelineChromeVisibility = getTimelineChromeVisibility({ isTimelineDragging });
  const activeActionRailResonanceCue = useMemo(
    () => {
      if (!isActionRailResonancePresentation(selectedPresentationType) || !isActive || !playbackState.isStarted) {
        return undefined;
      }
      const previewCue = getActionRailPreviewCue(selectedPresentationType);
      if (previewCue) {
        return completedResonanceCueIds.has(previewCue.cueId) ? undefined : previewCue;
      }
      return getActiveActionRailResonanceCue({
        cues: ACTION_RAIL_RESONANCE_CUES,
        currentTime,
        completedCueIds: completedResonanceCueIds
      });
    },
    [completedResonanceCueIds, currentTime, isActive, playbackState.isStarted, selectedPresentationType]
  );
  const actionRailResonanceCue = getVisibleActionRailResonanceCue({
    activeCue: activeActionRailResonanceCue,
    participatingCue: participatingResonanceCue
  });
  const displayVideo = playbackAssetVideo?.videoId === video.videoId ? playbackAssetVideo : video;

  useEffect(() => {
    let cancelled = false;
    const cached = playbackAssetCache.get(video.videoId);
    setPlaybackAssetVideo(cached?.storyboard ? { ...video, storyboard: cached.storyboard } : undefined);
    loadLightweightPlaybackAssets({
      apiBaseUrl: API_BASE_URL,
      videoId: video.videoId
    })
      .then((assets) => {
        if (!cancelled) {
          if (assets.storyboard) {
            playbackAssetCache.setStoryboard(video.videoId, assets.storyboard);
            prefetchStoryboardSheets({
              cache: playbackAssetCache,
              videoId: video.videoId,
              storyboard: assets.storyboard
            }).catch(() => undefined);
          }
          playbackAssetCache.setInteractionPlans(video.videoId, assets.interactionPlans);
          setPlaybackAssetVideo(assets.video);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [playbackAssetCache, video]);

  useEffect(() => {
    playbackObserver?.record({
      eventType: "page_mount",
      videoId: video.videoId,
      pageIndex
    });
    return () => {
      playbackObserver?.record({
        eventType: "page_unmount",
        videoId: video.videoId,
        pageIndex
      });
    };
  }, [pageIndex, playbackObserver, video.videoId]);

  useEffect(() => {
    playbackObserver?.record({
      eventType: "preload_state_change",
      videoId: video.videoId,
      pageIndex,
      details: { isPreloaded: videoRenderState.shouldRenderVideo }
    });
  }, [pageIndex, playbackObserver, videoRenderState.shouldRenderVideo, video.videoId]);

  useEffect(() => {
    playbackObserver?.record({
      eventType: "playback_ownership_change",
      videoId: video.videoId,
      pageIndex,
      details: { hasPlaybackOwnership: isActive }
    });
  }, [isActive, pageIndex, playbackObserver, video.videoId]);

  const clearResonanceTimers = useCallback(() => {
    if (resonanceButtonDismissTimeoutRef.current) {
      clearTimeout(resonanceButtonDismissTimeoutRef.current);
      resonanceButtonDismissTimeoutRef.current = undefined;
    }
    if (resonanceEffectTimeoutRef.current) {
      clearTimeout(resonanceEffectTimeoutRef.current);
      resonanceEffectTimeoutRef.current = undefined;
    }
  }, []);

  useEffect(() => clearResonanceTimers, [clearResonanceTimers]);

  const {
    dismiss: dismissInteractionExample,
    reset: resetInteractionExample,
    visible: isInteractionExampleVisible
  } = useInteractionExampleState({
    currentTime,
    example: DEFAULT_INTERACTION_EXAMPLE,
    isActive,
    isStarted: playbackState.isStarted,
    presentationType: selectedPresentationType,
    resetKey: video.videoId
  });

  const handleTogglePlay = useCallback(() => {
    if (!isActive) {
      return;
    }
    setUserPlaybackIntent((intent) => (intent === "playing" ? "paused" : "playing"));
  }, [isActive]);

  const handleResume = useCallback(() => {
    if (!isActive) {
      return;
    }
    setUserPlaybackIntent("playing");
  }, [isActive]);

  const speedControls = usePlaybackSpeedControls({
    isActive,
    isStarted: playbackState.isStarted,
    onResume: handleResume,
    onStart: handleResume,
    onTap: handleTogglePlay,
    resetKey: video.videoId
  });

  const mergedDanmaku = useMemo(
    () => [...danmaku, ...toDanmakuItems(sentInnerVoiceDanmaku)].sort((a, b) => a.time_sec - b.time_sec),
    [danmaku, sentInnerVoiceDanmaku]
  );

  useEffect(() => {
    if (!isActive) {
      wasActiveRef.current = false;
      return;
    }

    const becameActive = !wasActiveRef.current;
    const videoChanged = previousVideoIdRef.current !== video.videoId;
    if (becameActive || videoChanged) {
      const resumeTime = resumePlaybackTime;
      setCurrentTime(resumeTime);
      setResolvedDuration(video.duration);
      setUserPlaybackIntent("playing");
      setSeekRequest(undefined);
      setSeekVersion((version) => version + 1);
      setSentInnerVoiceDanmaku([]);
      setCompletedResonanceCueIds(new Set());
      setParticipatingResonanceCue(undefined);
      setResonanceTapState(createInitialResonanceTapState());
      resetInteractionExample();
      storyQaRequestRef.current += 1;
      setStoryQaState(resetStoryQaState());
      previousTimeRef.current = resumeTime;
      lastPublishedTimeRef.current = resumeTime;
      lastReportedPositionRef.current = resumeTime;
      didCompleteRef.current = false;
      previousVideoIdRef.current = video.videoId;
    }
    wasActiveRef.current = true;
  }, [isActive, resetInteractionExample, resumePlaybackTime, video.duration, video.videoId]);

  useEffect(() => {
    setResolvedDuration(video.duration);
  }, [video.duration, video.videoId]);

  useEffect(() => {
    clearResonanceTimers();
    setCompletedResonanceCueIds(new Set());
    setParticipatingResonanceCue(undefined);
    setResonanceTapState(createInitialResonanceTapState());
  }, [clearResonanceTimers, selectedPresentationType, video.videoId]);

  const handleTimeChange = useCallback(
    (time: number) => {
      if (isActive) {
        if (
          shouldResetExample({
            previousTime: previousTimeRef.current,
            currentTime: time,
            triggerTimeSec: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec
          })
        ) {
          resetInteractionExample();
        }
        if (
          shouldResetActionRailResonanceCue({
            previousTime: previousTimeRef.current,
            currentTime: time,
            firstTriggerTime: ACTION_RAIL_RESONANCE_CUES[0]?.triggerTime ?? 0
          })
        ) {
          clearResonanceTimers();
          setCompletedResonanceCueIds(new Set());
          setParticipatingResonanceCue(undefined);
          setResonanceTapState(createInitialResonanceTapState());
        }
        previousTimeRef.current = time;
        const previousPublishedTime = lastPublishedTimeRef.current;
        const isCloseToEnd = resolvedDuration > 0 && resolvedDuration - time <= 4;
        const didCountdownSecondChange =
          isCloseToEnd && Math.ceil(resolvedDuration - time) !== Math.ceil(resolvedDuration - previousPublishedTime);
        if (Math.abs(time - previousPublishedTime) >= UI_TIME_UPDATE_INTERVAL_SEC || didCountdownSecondChange) {
          lastPublishedTimeRef.current = time;
          setCurrentTime(time);
        }
        if (Math.abs(time - lastReportedPositionRef.current) >= UI_TIME_UPDATE_INTERVAL_SEC) {
          lastReportedPositionRef.current = time;
          onPlaybackPositionChange(video.videoId, time);
        }
        if (
          hasNextEpisode &&
          playbackState.shouldPlay &&
          resolvedDuration > 0 &&
          time >= Math.max(0, resolvedDuration - 0.2) &&
          !didCompleteRef.current
        ) {
          didCompleteRef.current = true;
          onPlayNextEpisode();
        }
      }
    },
    [
      hasNextEpisode,
      isActive,
      onPlayNextEpisode,
      onPlaybackPositionChange,
      playbackState.shouldPlay,
      resetInteractionExample,
      resolvedDuration,
      clearResonanceTimers,
      video.videoId
    ]
  );

  const handleDurationChange = useCallback((duration: number) => {
    setResolvedDuration(duration);
  }, []);

  const handlePlayToEnd = useCallback(() => {
    if (!isActive || !hasNextEpisode || didCompleteRef.current) {
      return;
    }
    didCompleteRef.current = true;
    onPlayNextEpisode();
  }, [hasNextEpisode, isActive, onPlayNextEpisode]);

  const handleSeekHandled = useCallback(() => {
    setSeekRequest(undefined);
  }, []);

  const handleSeekCommit = useCallback(
    (time: number) => {
      if (!isActive) {
        return;
      }
      setCurrentTime(time);
      lastPublishedTimeRef.current = time;
      previousTimeRef.current = time;
      lastReportedPositionRef.current = time;
      onPlaybackPositionChange(video.videoId, time);
      didCompleteRef.current = false;
      if (time < DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec) {
        resetInteractionExample();
      }
      if (time < (ACTION_RAIL_RESONANCE_CUES[0]?.triggerTime ?? 0)) {
        clearResonanceTimers();
        setCompletedResonanceCueIds(new Set());
        setParticipatingResonanceCue(undefined);
        setResonanceTapState(createInitialResonanceTapState());
      }
      setUserPlaybackIntent("playing");
      setSeekVersion((version) => version + 1);
      setSeekRequest({ id: Date.now(), time, reason: "user_seek" });
    },
    [clearResonanceTimers, isActive, onPlaybackPositionChange, resetInteractionExample, video.videoId]
  );

  const handleTimelineDragStateChange = useCallback(
    (isDragging: boolean) => {
      setIsTimelineDragging(isDragging);
      onTimelineDragStateChange?.(isDragging);
    },
    [onTimelineDragStateChange]
  );

  const handleInnerVoiceGestureActiveChange = useCallback(
    (isGestureActive: boolean) => {
      onTimelineDragStateChange?.(isGestureActive);
    },
    [onTimelineDragStateChange]
  );

  const handleSendInnerVoiceDanmaku = useCallback(
    (cue: InnerVoiceDanmakuCue) => {
      setSentInnerVoiceDanmaku((items) => [
        ...items,
        createSentInnerVoiceDanmakuFromCue({
          cue,
          currentTime
        })
      ]);
    },
    [currentTime]
  );

  const handleParticipateResonance = useCallback((cue: ActionRailResonanceCue, nextState: ResonanceTapState) => {
    clearResonanceTimers();
    setParticipatingResonanceCue(cue);
    setResonanceTapState(nextState);
    resonanceButtonDismissTimeoutRef.current = setTimeout(() => {
      setCompletedResonanceCueIds((ids) => new Set(ids).add(cue.cueId));
      resonanceButtonDismissTimeoutRef.current = undefined;
    }, ACTION_RAIL_RESONANCE_BUTTON_DISMISS_DELAY_MS);
    resonanceEffectTimeoutRef.current = setTimeout(() => {
      setParticipatingResonanceCue(undefined);
      setResonanceTapState(createInitialResonanceTapState());
      resonanceEffectTimeoutRef.current = undefined;
    }, ACTION_RAIL_RESONANCE_EFFECT_HOLD_MS);
    // First version records locally. Future API wiring can report cueId/highlightId/tapCount here.
    void nextState;
  }, [clearResonanceTimers]);

  useEffect(() => {
    if (activeActionRailResonanceCue || participatingResonanceCue) {
      return;
    }
    if (!isActionRailResonancePresentation(selectedPresentationType)) {
      return;
    }
    const expiredCue = ACTION_RAIL_RESONANCE_CUES.find(
      (cue) =>
        !completedResonanceCueIds.has(cue.cueId) &&
        currentTime > cue.triggerTime + cue.durationSec &&
        previousTimeRef.current >= cue.triggerTime
    );
    if (expiredCue) {
      setCompletedResonanceCueIds((ids) => new Set(ids).add(expiredCue.cueId));
    }
  }, [
    activeActionRailResonanceCue,
    completedResonanceCueIds,
    currentTime,
    participatingResonanceCue,
    selectedPresentationType
  ]);

  const handleSubmitStoryQa = useCallback(
    (quickQuestion?: string) => {
      const nextQuestion = (quickQuestion ?? storyQaState.question).trim();
      setStoryQaState((state) => ({
        ...state,
        question: nextQuestion,
        error: undefined,
        answer: undefined
      }));
      if (!nextQuestion) {
        setStoryQaState((state) => ({ ...state, error: "请输入问题" }));
        return;
      }
      const context = resolveStoryQaContext(video);
      const requestId = storyQaRequestRef.current + 1;
      storyQaRequestRef.current = requestId;
      setStoryQaState((state) => ({ ...state, isLoading: true }));
      askStoryQa({
        apiBaseUrl: API_BASE_URL,
        question: nextQuestion,
        seriesId: context.seriesId,
        currentEpisode: context.currentEpisode,
        currentTime
      })
        .then((result) => {
          if (storyQaRequestRef.current === requestId) {
            setStoryQaState((state) => ({ ...state, answer: result.answer }));
          }
        })
        .catch((error: unknown) => {
          if (storyQaRequestRef.current === requestId) {
            setStoryQaState((state) => ({
              ...state,
              error: error instanceof Error ? error.message : "剧情问答暂时不可用"
            }));
          }
        })
        .finally(() => {
          if (storyQaRequestRef.current === requestId) {
            setStoryQaState((state) => ({ ...state, isLoading: false }));
          }
        });
    },
    [currentTime, storyQaState.question, video]
  );

  return (
    <View style={[styles.root, { height }]}>
      <View style={[styles.videoViewport, { height: videoHeight }]}>
        {renderState.shouldRenderVideo ? (
          <VideoStage
            key={`${video.videoId}:${video.streamUrl}`}
            observation={videoObservation}
            isStarted={playbackState.isStarted}
            isPlaying={playbackState.shouldPlay}
            initialPlaybackTime={resumePlaybackTime}
            seekRequest={seekRequest}
            onStart={handleResume}
            onTimeChange={handleTimeChange}
            onDurationChange={handleDurationChange}
            onPlayToEnd={handlePlayToEnd}
            onSeekHandled={handleSeekHandled}
            onFirstFrameRender={onFirstFrameRender}
            playbackRate={speedControls.effectivePlaybackRate}
            bufferOptions={videoBufferOptions}
            enableCaching={FEED_VIDEO_SOURCE_CACHING_ENABLED}
            showStartEntry={false}
            streamUrl={video.streamUrl}
          />
        ) : (
          <View style={styles.inactiveVideoPlaceholder} />
        )}
        {isActive && playbackState.isStarted && danmakuState === "ready" ? (
          <DanmakuLayer
            currentTime={currentTime}
            danmaku={mergedDanmaku}
            isPlaying={playbackState.shouldPlay}
            seekVersion={seekVersion}
          />
        ) : null}
        {isActive && playbackState.isStarted ? <Pressable style={styles.tapLayer} onPress={handleTogglePlay} /> : null}
        {renderState.shouldRenderInteractiveShell ? <PlaybackHint visible={playbackState.shouldShowPauseHint} /> : null}
      </View>
      {mode === "home" ? (
        <PlayerBottomTabs activeTab="首页" presentation="docked" onPressTheater={onOpenTheater} />
      ) : null}
      {mode === "series" ? (
        <View style={[styles.seriesBottomDock, { height: Math.max(0, height - videoHeight) }]} />
      ) : null}
      {isActive && playbackState.isStarted ? (
        <FastForwardPressLayer
          isHoldingFastForward={speedControls.isHoldingFastForward}
          bottomOffset={metaBottomOffset}
          onPress={speedControls.handleRightPress}
          onLongPress={speedControls.handleRightLongPress}
          onPressOut={speedControls.handleRightPressOut}
        />
      ) : null}
      {isActive && danmakuState === "error" ? <Text style={styles.danmakuError}>弹幕暂不可用</Text> : null}
      {renderState.shouldRenderInteractiveShell ? (
        <ActionRailResonanceBurstLayer
          cue={participatingResonanceCue}
          tapCount={resonanceTapState.tapCount}
          releaseCount={resonanceTapState.releaseCount}
        />
      ) : null}
      {isInteractionExampleVisible && selectedPresentationType === "danmaku_poll" ? (
        <DanmakuPollExample example={DEFAULT_INTERACTION_EXAMPLE} onDismiss={dismissInteractionExample} />
      ) : null}
      {renderState.shouldRenderInteractiveShell ? (
        <PlayerChrome
          liked={liked}
          onToggleLike={() => setLiked((current) => !current)}
          onOpenStoryQa={() => setStoryQaState((state) => ({ ...state, isOpen: true }))}
          onOpenTheater={onOpenTheater}
          onBack={onBack}
          playbackRate={speedControls.playbackRate}
          isSpeedMenuOpen={speedControls.isSpeedMenuOpen}
          onToggleSpeedMenu={speedControls.toggleSpeedMenu}
          onSelectPlaybackRate={speedControls.selectPlaybackRate}
          title={displayVideo.title}
          plotSummary={displayVideo.plotSummary}
          episodeLabel={displayVideo.episodeLabel}
          metaBottomOffset={metaBottomOffset}
          actionRailBottomOffset={actionRailBottomOffset}
          showActionRail={timelineChromeVisibility.showActionRail}
          showMeta={timelineChromeVisibility.showMeta}
          mode={mode}
          currentTime={currentTime}
          isActive={isActive && playbackState.isStarted}
          showInnerVoice={selectedPresentationType === "inner_voice_danmaku"}
          onInnerVoiceGestureActiveChange={handleInnerVoiceGestureActiveChange}
          onSendInnerVoiceDanmaku={handleSendInnerVoiceDanmaku}
          resonanceCue={actionRailResonanceCue}
          resonanceTapState={resonanceTapState}
          onParticipateResonance={handleParticipateResonance}
        >
          {mode === "series" && seriesEpisodeCount !== undefined && onOpenSeriesDetail ? (
            <SeriesEpisodeBar episodeCount={seriesEpisodeCount} onPress={onOpenSeriesDetail} />
          ) : null}
        </PlayerChrome>
      ) : null}
      {ENABLE_INTERACTION_LAB && isActive ? (
        <InteractionLabControls selectedType={selectedPresentationType} onChange={onChangePresentationType} />
      ) : null}
      {renderState.shouldRenderPlaybackControls ? (
        <PlayerControls
          currentTime={currentTime}
          duration={resolvedDuration}
          hasNextEpisode={hasNextEpisode}
          nextEpisodeLabel={nextEpisodeLabel}
          bottomOffset={controlsBottomOffset}
          onSeekCommit={handleSeekCommit}
          onDragStateChange={handleTimelineDragStateChange}
          storyChapters={displayVideo.storyChapters}
          storyboard={displayVideo.storyboard}
        />
      ) : null}
      {renderState.shouldRenderInteractiveShell ? (
        <StoryQaPanel
          visible={storyQaState.isOpen}
          question={storyQaState.question}
          answer={storyQaState.answer}
          error={storyQaState.error}
          isLoading={storyQaState.isLoading}
          onChangeQuestion={(question) => setStoryQaState((state) => ({ ...state, question }))}
          onSubmit={handleSubmitStoryQa}
          onClose={() => setStoryQaState((state) => ({ ...state, isOpen: false }))}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    backgroundColor: "#050505",
    overflow: "hidden"
  },
  videoViewport: {
    overflow: "hidden",
    backgroundColor: "#050505"
  },
  seriesBottomDock: {
    backgroundColor: "#1C1C1E"
  },
  inactiveVideoPlaceholder: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#050505"
  },
  tapLayer: {
    ...StyleSheet.absoluteFillObject
  },
  danmakuError: {
    position: "absolute",
    top: 92,
    alignSelf: "center",
    color: "rgba(255,255,255,0.68)",
    fontSize: 12,
    fontWeight: "700",
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: "rgba(0,0,0,0.36)",
    borderRadius: 6
  }
});
