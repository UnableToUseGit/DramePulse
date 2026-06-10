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
import { API_BASE_URL, ENABLE_INTERACTION_LAB, ENABLE_PLAYBACK_DEBUG_PANEL } from "../config";
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
import {
  getExpiredInteractionCueIds,
  getSeekSkippedInteractionCueIds,
  toActionRailResonanceCues,
  toInnerVoiceDanmakuCues,
  toInteractionDebugMarkers
} from "../domain/interactionAssetCues";
import { InteractionAsset, loadLightweightPlaybackAssets } from "../domain/playerDataApi";
import { resolveStoryQaContext } from "../domain/storyQa";
import {
  askWatchAssistant,
  WatchAssistantAction,
  WatchAssistantToolCall,
  WatchAssistantTranscription
} from "../domain/watchAssistant";
import { FEED_VIDEO_SOURCE_CACHING_ENABLED, getFeedVideoBufferOptions } from "../domain/videoSource";
import { useDanmakuFeed } from "../hooks/useDanmakuFeed";
import { useInteractionExampleState } from "../hooks/useInteractionExampleState";
import { usePlaybackSpeedControls } from "../hooks/usePlaybackSpeedControls";
import { createSentInnerVoiceDanmakuFromCue, toDanmakuItems } from "../inner-voice-danmaku/sentDanmaku";
import { getActiveInnerVoiceCue, getVisibleInnerVoiceCue } from "../inner-voice-danmaku/scheduler";
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
import { WatchAssistantPanel } from "./WatchAssistantPanel";
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
  onPlaybackReady?: () => void;
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

interface WatchAssistantPanelState {
  isOpen: boolean;
  message: string;
  reply?: string;
  error?: string;
  isLoading: boolean;
  voiceState: "idle" | "recording" | "transcribing";
  voiceMeta?: WatchAssistantTranscription;
  toolCalls: WatchAssistantToolCall[];
  executionHint?: string;
}

function resetWatchAssistantState(): WatchAssistantPanelState {
  return {
    isOpen: false,
    message: "",
    reply: undefined,
    error: undefined,
    isLoading: false,
    voiceState: "idle",
    voiceMeta: undefined,
    toolCalls: [],
    executionHint: undefined
  };
}

function isWebMicrophoneBlockedByInsecureOrigin(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const hostname = window.location.hostname;
  const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  return window.isSecureContext === false && !isLocalhost;
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
  onPlaybackReady,
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
  const [completedInteractionCueIds, setCompletedInteractionCueIds] = useState<Set<string>>(() => new Set());
  const [participatingResonanceCue, setParticipatingResonanceCue] = useState<ActionRailResonanceCue | undefined>();
  const [launchingInnerVoiceCue, setLaunchingInnerVoiceCue] = useState<InnerVoiceDanmakuCue | undefined>();
  const [resonanceTapState, setResonanceTapState] = useState<ResonanceTapState>(() =>
    createInitialResonanceTapState()
  );
  const [assistantState, setAssistantState] = useState<WatchAssistantPanelState>(() => resetWatchAssistantState());
  const [interactionAssets, setInteractionAssets] = useState<InteractionAsset[]>(
    () => playbackAssetCache.get(video.videoId)?.interactionAssets ?? []
  );
  const [playbackAssetVideo, setPlaybackAssetVideo] = useState<PlayerVideo | undefined>(() => {
    const cached = playbackAssetCache.get(video.videoId);
    return cached?.storyboard || cached?.storyChapters
      ? {
          ...video,
          ...(cached.storyboard ? { storyboard: cached.storyboard } : {}),
          ...(cached.storyChapters ? { storyChapters: cached.storyChapters } : {})
        }
      : undefined;
  });
  const previousTimeRef = useRef(0);
  const lastPublishedTimeRef = useRef(0);
  const didCompleteRef = useRef(false);
  const wasActiveRef = useRef(false);
  const previousVideoIdRef = useRef(video.videoId);
  const lastReportedPositionRef = useRef(0);
  const assistantRequestRef = useRef(0);
  const resonanceButtonDismissTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const resonanceEffectTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const playbackState = getVideoPlaybackState({ isActive, userPlaybackIntent });
  const shouldLoadDanmaku = isActive && playbackState.isStarted;
  const { danmaku, danmakuState } = useDanmakuFeed(video.danmakuUrl, shouldLoadDanmaku, currentTime);
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
  const apiActionRailCues = useMemo(() => toActionRailResonanceCues(interactionAssets), [interactionAssets]);
  const apiInnerVoiceCues = useMemo(() => toInnerVoiceDanmakuCues(interactionAssets), [interactionAssets]);
  const debugInteractionMarkers = useMemo(
    () => (ENABLE_PLAYBACK_DEBUG_PANEL ? toInteractionDebugMarkers(interactionAssets) : []),
    [interactionAssets]
  );
  const activeApiActionRailResonanceCue = useMemo(
    () =>
      isActive && playbackState.isStarted
        ? getActiveActionRailResonanceCue({
            cues: apiActionRailCues,
            currentTime,
            completedCueIds: completedInteractionCueIds
          })
        : undefined,
    [apiActionRailCues, completedInteractionCueIds, currentTime, isActive, playbackState.isStarted]
  );
  const activeActionRailResonanceCue = useMemo(
    () => {
      if (activeApiActionRailResonanceCue) {
        return activeApiActionRailResonanceCue;
      }
      if (!ENABLE_INTERACTION_LAB) {
        return undefined;
      }
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
    [
      activeApiActionRailResonanceCue,
      completedResonanceCueIds,
      currentTime,
      isActive,
      playbackState.isStarted,
      selectedPresentationType
    ]
  );
  const actionRailResonanceCue = getVisibleActionRailResonanceCue({
    activeCue: activeActionRailResonanceCue,
    participatingCue: participatingResonanceCue
  });
  const activeApiInnerVoiceCue = useMemo(
    () =>
      isActive && playbackState.isStarted
        ? getActiveInnerVoiceCue({
            cues: apiInnerVoiceCues,
            currentTime,
            completedCueIds: completedInteractionCueIds
          })
        : undefined,
    [apiInnerVoiceCues, completedInteractionCueIds, currentTime, isActive, playbackState.isStarted]
  );
  const innerVoiceCue = getVisibleInnerVoiceCue({
    activeCue: activeApiInnerVoiceCue,
    launchingCue: launchingInnerVoiceCue
  });
  const displayVideo = playbackAssetVideo?.videoId === video.videoId ? playbackAssetVideo : video;

  useEffect(() => {
    let cancelled = false;
    const cached = playbackAssetCache.get(video.videoId);
    setInteractionAssets(cached?.interactionAssets ?? []);
    setPlaybackAssetVideo(
      cached?.storyboard || cached?.storyChapters
        ? {
            ...video,
            ...(cached.storyboard ? { storyboard: cached.storyboard } : {}),
            ...(cached.storyChapters ? { storyChapters: cached.storyChapters } : {})
          }
        : undefined
    );
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
          playbackAssetCache.setStoryChapters(video.videoId, assets.storyChapters);
          playbackAssetCache.setInteractionAssets(video.videoId, assets.interactionAssets);
          setInteractionAssets(assets.interactionAssets);
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
      if (videoChanged) {
        setCompletedInteractionCueIds(new Set());
      }
      setParticipatingResonanceCue(undefined);
      setLaunchingInnerVoiceCue(undefined);
      setResonanceTapState(createInitialResonanceTapState());
      resetInteractionExample();
      assistantRequestRef.current += 1;
      setAssistantState(resetWatchAssistantState());
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
      const skippedCueIds = getSeekSkippedInteractionCueIds({
        cues: [...apiActionRailCues, ...apiInnerVoiceCues],
        seekTime: time,
        completedCueIds: completedInteractionCueIds
      });
      if (skippedCueIds.length > 0) {
        setCompletedInteractionCueIds((ids) => new Set([...ids, ...skippedCueIds]));
        setLaunchingInnerVoiceCue((cue) => (cue && skippedCueIds.includes(cue.cueId) ? undefined : cue));
      }
      setUserPlaybackIntent("playing");
      setSeekVersion((version) => version + 1);
      setSeekRequest({ id: Date.now(), time, reason: "user_seek" });
    },
    [
      apiActionRailCues,
      apiInnerVoiceCues,
      clearResonanceTimers,
      completedInteractionCueIds,
      isActive,
      onPlaybackPositionChange,
      resetInteractionExample,
      video.videoId
    ]
  );

  const handleTimelineDragStateChange = useCallback(
    (isDragging: boolean) => {
      setIsTimelineDragging(isDragging);
      onTimelineDragStateChange?.(isDragging);
    },
    [onTimelineDragStateChange]
  );

  const reportAssistantPlaybackEvent = useCallback(
    (action: WatchAssistantAction, rawMessage: string, inputMode: "text" | "voice", voiceMeta?: WatchAssistantTranscription) => {
      const eventType =
        action.type === "pause"
          ? "pause"
          : action.type === "resume"
            ? "resume"
            : action.type === "seek"
              ? (typeof action.relativeSeconds === "number" && action.relativeSeconds < 0 ? "seek_backward" : "seek_forward")
              : undefined;
      if (!eventType) {
        return;
      }
      fetch(`${API_BASE_URL.replace(/\/$/, "")}/api/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: eventType,
          user_id: "u_demo_001",
          video_id: video.videoId,
          client_time: currentTime,
          timestamp: Date.now(),
          extra: {
            source: "watch_assistant",
            input_mode: inputMode,
            assistant_action: action.type,
            raw_message: rawMessage,
            transcript: inputMode === "voice" ? rawMessage : undefined,
            asr_confidence: voiceMeta?.confidence,
            audio_duration_ms: voiceMeta?.durationMs,
            target_time: action.targetTime
          }
        })
      }).catch(() => undefined);
    },
    [currentTime, video.videoId]
  );

  const applyAssistantActions = useCallback(
    (
      actions: WatchAssistantAction[],
      rawMessage: string,
      inputMode: "text" | "voice",
      voiceMeta?: WatchAssistantTranscription
    ): string | undefined => {
      let hint: string | undefined;
      actions.forEach((action) => {
        if (action.type === "seek" && typeof action.targetTime === "number") {
          handleSeekCommit(action.targetTime);
          reportAssistantPlaybackEvent(action, rawMessage, inputMode, voiceMeta);
          hint = "已执行跳转";
          return;
        }
        if (action.type === "next_episode") {
          if (!hasNextEpisode) {
            hint = "已经是最后一集";
            return;
          }
          onPlayNextEpisode();
          hint = "已切到下一集";
          return;
        }
        if (action.type === "pause") {
          setUserPlaybackIntent("paused");
          reportAssistantPlaybackEvent(action, rawMessage, inputMode, voiceMeta);
          hint = "已暂停";
          return;
        }
        if (action.type === "resume") {
          setUserPlaybackIntent("playing");
          reportAssistantPlaybackEvent(action, rawMessage, inputMode, voiceMeta);
          hint = "继续播放";
        }
      });
      return hint;
    },
    [handleSeekCommit, hasNextEpisode, onPlayNextEpisode, reportAssistantPlaybackEvent]
  );

  const handleInnerVoiceGestureActiveChange = useCallback(
    (isGestureActive: boolean) => {
      onTimelineDragStateChange?.(isGestureActive);
    },
    [onTimelineDragStateChange]
  );

  const handleSendInnerVoiceDanmaku = useCallback(
    (cue: InnerVoiceDanmakuCue) => {
      setLaunchingInnerVoiceCue(cue);
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

  const handleInnerVoiceExitComplete = useCallback((cue: InnerVoiceDanmakuCue) => {
    setCompletedInteractionCueIds((ids) => new Set(ids).add(cue.cueId));
    setLaunchingInnerVoiceCue((current) => (current?.cueId === cue.cueId ? undefined : current));
  }, []);

  const handleParticipateResonance = useCallback((cue: ActionRailResonanceCue, nextState: ResonanceTapState) => {
    clearResonanceTimers();
    setParticipatingResonanceCue(cue);
    setResonanceTapState(nextState);
    resonanceButtonDismissTimeoutRef.current = setTimeout(() => {
      setCompletedResonanceCueIds((ids) => new Set(ids).add(cue.cueId));
      setCompletedInteractionCueIds((ids) => new Set(ids).add(cue.cueId));
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
    const expiredCueIds = getExpiredInteractionCueIds({
      cues: [...apiActionRailCues, ...apiInnerVoiceCues],
      currentTime,
      completedCueIds: completedInteractionCueIds
    });
    if (expiredCueIds.length > 0) {
      setCompletedInteractionCueIds((ids) => new Set([...ids, ...expiredCueIds]));
      setLaunchingInnerVoiceCue((cue) => (cue && expiredCueIds.includes(cue.cueId) ? undefined : cue));
    }
  }, [apiActionRailCues, apiInnerVoiceCues, completedInteractionCueIds, currentTime]);

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

  const handleSubmitWatchAssistant = useCallback(
    (quickMessage?: string, inputMode: "text" | "voice" = "text", voiceMeta?: WatchAssistantTranscription) => {
      const nextMessage = (quickMessage ?? assistantState.message).trim();
      setAssistantState((state) => ({
        ...state,
        message: nextMessage,
        error: undefined,
        reply: undefined,
        voiceMeta,
        executionHint: undefined,
        toolCalls: []
      }));
      if (!nextMessage) {
        setAssistantState((state) => ({ ...state, error: "请输入指令或剧情问题" }));
        return;
      }
      const context = resolveStoryQaContext(video);
      const requestId = assistantRequestRef.current + 1;
      assistantRequestRef.current = requestId;
      setAssistantState((state) => ({ ...state, isLoading: true }));
      askWatchAssistant({
        apiBaseUrl: API_BASE_URL,
        message: nextMessage,
        seriesId: context.seriesId,
        videoId: video.videoId,
        currentEpisode: context.currentEpisode,
        currentTime,
        duration: resolvedDuration
      })
        .then((response) => {
          if (assistantRequestRef.current === requestId) {
            const executionHint = applyAssistantActions(response.actions, nextMessage, inputMode, voiceMeta);
            setAssistantState((state) => ({
              ...state,
              reply: response.reply,
              toolCalls: response.toolCalls,
              executionHint
            }));
          }
        })
        .catch((error: unknown) => {
          if (assistantRequestRef.current === requestId) {
            setAssistantState((state) => ({
              ...state,
              error: error instanceof Error ? error.message : "观看助手暂时不可用"
            }));
          }
        })
        .finally(() => {
          if (assistantRequestRef.current === requestId) {
            setAssistantState((state) => ({ ...state, isLoading: false }));
          }
        });
    },
    [applyAssistantActions, assistantState.message, currentTime, resolvedDuration, video]
  );

  const handleToggleVoiceRecording = useCallback(async () => {
    if (assistantState.isLoading) {
      return;
    }
    try {
      if (isWebMicrophoneBlockedByInsecureOrigin()) {
        throw new Error("当前页面不是 HTTPS，浏览器不会弹出麦克风授权。请使用 HTTPS 或本地 localhost 访问。");
      }
      await import("expo-audio");
      setAssistantState((state) => ({
        ...state,
        voiceState: "idle",
        error: "当前先用文本调试 Watch Assistant；语音录制留到 development build 阶段启用。"
      }));
    } catch (error) {
      setAssistantState((state) => ({
        ...state,
        voiceState: "idle",
        error:
          error instanceof Error && error.message.includes("HTTPS")
            ? error.message
            : "Expo Go 不包含 ExpoAudio 原生模块。当前先用文本调试，语音输入需要 development build。"
      }));
    }
  }, [assistantState.isLoading]);

  const handleCancelVoiceRecording = useCallback(() => {
    setAssistantState((state) => ({ ...state, voiceState: "idle" }));
  }, []);

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
            onPlaybackReady={onPlaybackReady}
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
            playbackRate={speedControls.effectivePlaybackRate}
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
      {ENABLE_INTERACTION_LAB && isInteractionExampleVisible && selectedPresentationType === "danmaku_poll" ? (
        <DanmakuPollExample example={DEFAULT_INTERACTION_EXAMPLE} onDismiss={dismissInteractionExample} />
      ) : null}
      {renderState.shouldRenderInteractiveShell ? (
        <PlayerChrome
          liked={liked}
          onToggleLike={() => setLiked((current) => !current)}
          onOpenWatchAssistant={() => {
            setAssistantState((state) => ({ ...state, isOpen: true }));
          }}
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
          innerVoiceCue={innerVoiceCue}
          showInnerVoiceExample={ENABLE_INTERACTION_LAB && selectedPresentationType === "inner_voice_danmaku"}
          onInnerVoiceGestureActiveChange={handleInnerVoiceGestureActiveChange}
          onSendInnerVoiceDanmaku={handleSendInnerVoiceDanmaku}
          onInnerVoiceExitComplete={handleInnerVoiceExitComplete}
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
          debugInteractionMarkers={debugInteractionMarkers}
        />
      ) : null}
      {renderState.shouldRenderInteractiveShell ? (
        <WatchAssistantPanel
          visible={assistantState.isOpen}
          message={assistantState.message}
          reply={assistantState.reply}
          error={assistantState.error}
          isLoading={assistantState.isLoading}
          voiceState={assistantState.voiceState}
          voiceDurationSec={0}
          toolCalls={assistantState.toolCalls}
          executionHint={assistantState.executionHint}
          onChangeMessage={(message) => setAssistantState((state) => ({ ...state, message }))}
          onSubmit={handleSubmitWatchAssistant}
          onToggleVoiceRecording={handleToggleVoiceRecording}
          onCancelVoiceRecording={handleCancelVoiceRecording}
          onClose={() => setAssistantState((state) => ({ ...state, isOpen: false }))}
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
