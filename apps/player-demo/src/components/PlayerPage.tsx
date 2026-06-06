import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder, useAudioRecorderState } from "expo-audio";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { API_BASE_URL, ENABLE_INTERACTION_LAB } from "../config";
import { getFeedPlaybackMode } from "../domain/playerFeed";
import { loadVideoDanmaku, PlayerVideo } from "../domain/playerApi";
import { resolveStoryQaContext } from "../domain/storyQa";
import {
  askWatchAssistant,
  transcribeWatchAssistantAudio,
  WatchAssistantAction,
  WatchAssistantToolCall,
  WatchAssistantTranscription
} from "../domain/watchAssistant";
import type { DanmakuItem } from "../domain/types";
import { DEFAULT_INTERACTION_EXAMPLE } from "../interaction-examples/examples";
import { InteractionExampleRenderer } from "../interaction-examples/InteractionExampleRenderer";
import { InteractionLabControls } from "../interaction-examples/InteractionLabControls";
import { shouldResetExample, shouldShowExample } from "../interaction-examples/trigger";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { colors, spacing } from "../theme";
import { DanmakuLayer } from "./DanmakuLayer";
import { PlaybackHint } from "./PlaybackHint";
import { PlayerChrome } from "./PlayerChrome";
import { PlayerControls } from "./PlayerControls";
import { SeekRequest, VideoStage } from "./VideoStage";
import { WatchAssistantPanel } from "./WatchAssistantPanel";

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

const MAX_VOICE_RECORDING_SECONDS = 10;

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
  isActive,
  height,
  hasStartedFeed,
  selectedPresentationType,
  onChangePresentationType,
  onRequestNextEpisode,
  onStartFeed
}: {
  video: PlayerVideo;
  isActive: boolean;
  height: number;
  hasStartedFeed: boolean;
  selectedPresentationType: InteractionPresentationType;
  onChangePresentationType: (type: InteractionPresentationType) => void;
  onRequestNextEpisode: () => boolean;
  onStartFeed: () => void;
}) {
  const [danmaku, setDanmaku] = useState<DanmakuItem[]>([]);
  const [danmakuState, setDanmakuState] = useState<"loading" | "ready" | "error">("loading");
  const [currentTime, setCurrentTime] = useState(0);
  const [mediaDuration, setMediaDuration] = useState(0);
  const [isStarted, setIsStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [seekVersion, setSeekVersion] = useState(0);
  const [exampleDismissed, setExampleDismissed] = useState(false);
  const [assistantState, setAssistantState] = useState<WatchAssistantPanelState>(() => resetWatchAssistantState());
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const audioRecorderState = useAudioRecorderState(audioRecorder, 250);
  const previousTimeRef = useRef(0);
  const assistantRequestRef = useRef(0);
  const playbackMode = useMemo(
    () => getFeedPlaybackMode({ hasStartedFeed, isActive }),
    [hasStartedFeed, isActive]
  );
  const canPlay = isActive && isStarted && isPlaying;
  const effectiveDuration = mediaDuration > 0 ? mediaDuration : video.duration;

  useEffect(() => {
    let cancelled = false;
    setDanmakuState("loading");
    setDanmaku([]);
    loadVideoDanmaku({ danmakuUrl: video.danmakuUrl })
      .then((items) => {
        if (!cancelled) {
          setDanmaku(items);
          setDanmakuState("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDanmaku([]);
          setDanmakuState("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [video.danmakuUrl]);

  useEffect(() => {
    if (!isActive) {
      setIsPlaying(false);
      return;
    }
    setCurrentTime(0);
    setMediaDuration(0);
    setIsStarted(playbackMode.shouldAutoStart);
    setIsPlaying(playbackMode.shouldAutoStart);
    setSeekRequest({ id: Date.now(), time: 0 });
    setSeekVersion((version) => version + 1);
    setExampleDismissed(false);
    assistantRequestRef.current += 1;
    setAssistantState(resetWatchAssistantState());
    previousTimeRef.current = 0;
  }, [isActive, playbackMode.shouldAutoStart, video.videoId]);

  useEffect(() => {
    if (playbackMode.shouldAutoStart && !isStarted) {
      setIsStarted(true);
      setIsPlaying(true);
    }
  }, [isStarted, playbackMode.shouldAutoStart]);

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
          setExampleDismissed(false);
        }
        previousTimeRef.current = time;
        setCurrentTime(time);
      }
    },
    [isActive]
  );

  useEffect(() => {
    setExampleDismissed(false);
  }, [selectedPresentationType, video.videoId]);

  const handleStart = useCallback(() => {
    if (!isActive) {
      return;
    }
    onStartFeed();
    setIsStarted(true);
    setIsPlaying(true);
  }, [isActive, onStartFeed]);

  const handleTogglePlay = useCallback(() => {
    if (!isActive) {
      return;
    }
    if (!isStarted) {
      handleStart();
      return;
    }
    setIsPlaying((playing) => !playing);
  }, [handleStart, isActive, isStarted]);

  const handleSeekCommit = useCallback(
    (time: number) => {
      if (!isActive) {
        return;
      }
      setCurrentTime(time);
      previousTimeRef.current = time;
      if (time < DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec) {
        setExampleDismissed(false);
      }
      setIsStarted(true);
      setSeekVersion((version) => version + 1);
      setSeekRequest({ id: Date.now(), time });
    },
    [isActive]
  );

  const handleDismissExample = useCallback(() => {
    setExampleDismissed(true);
  }, []);

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
          const moved = onRequestNextEpisode();
          hint = moved ? "已切到下一集" : "已经是最后一集";
          return;
        }
        if (action.type === "pause") {
          setIsStarted(true);
          setIsPlaying(false);
          reportAssistantPlaybackEvent(action, rawMessage, inputMode, voiceMeta);
          hint = "已暂停";
          return;
        }
        if (action.type === "resume") {
          onStartFeed();
          setIsStarted(true);
          setIsPlaying(true);
          reportAssistantPlaybackEvent(action, rawMessage, inputMode, voiceMeta);
          hint = "继续播放";
        }
      });
      return hint;
    },
    [handleSeekCommit, onRequestNextEpisode, onStartFeed, reportAssistantPlaybackEvent]
  );

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
        duration: video.duration
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
    [applyAssistantActions, assistantState.message, currentTime, video]
  );

  const stopVoiceRecording = useCallback(
    async (shouldSubmit: boolean) => {
      if (assistantState.voiceState !== "recording") {
        return;
      }
      try {
        await audioRecorder.stop();
        const audioUri = audioRecorder.uri;
        if (!shouldSubmit) {
          setAssistantState((state) => ({ ...state, voiceState: "idle", error: undefined }));
          return;
        }
        if (!audioUri) {
          throw new Error("没有可上传的录音");
        }
        const context = resolveStoryQaContext(video);
        setAssistantState((state) => ({ ...state, voiceState: "transcribing", error: undefined, reply: undefined }));
        const transcription = await transcribeWatchAssistantAudio({
          apiBaseUrl: API_BASE_URL,
          audioUri,
          seriesId: context.seriesId,
          videoId: video.videoId,
          currentEpisode: context.currentEpisode,
          currentTime,
          duration: audioRecorderState.durationMillis / 1000
        });
        setAssistantState((state) => ({ ...state, message: transcription.text, voiceState: "idle", voiceMeta: transcription }));
        handleSubmitWatchAssistant(transcription.text, "voice", transcription);
      } catch (error) {
        setAssistantState((state) => ({
          ...state,
          voiceState: "idle",
          error: error instanceof Error ? error.message : "语音输入暂时不可用"
        }));
      } finally {
        await setAudioModeAsync({ allowsRecording: false }).catch(() => undefined);
      }
    },
    [assistantState.voiceState, audioRecorder, audioRecorderState.durationMillis, currentTime, handleSubmitWatchAssistant, video]
  );

  const handleToggleVoiceRecording = useCallback(async () => {
    if (assistantState.voiceState === "recording") {
      await stopVoiceRecording(true);
      return;
    }
    if (assistantState.voiceState !== "idle" || assistantState.isLoading) {
      return;
    }
    try {
      if (isWebMicrophoneBlockedByInsecureOrigin()) {
        throw new Error("当前页面不是 HTTPS，浏览器不会弹出麦克风授权。请使用 HTTPS 或本地 localhost 访问。");
      }
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        throw new Error("需要麦克风权限才能使用语音输入");
      }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await audioRecorder.prepareToRecordAsync();
      audioRecorder.record({ forDuration: MAX_VOICE_RECORDING_SECONDS });
      setAssistantState((state) => ({
        ...state,
        voiceState: "recording",
        error: undefined,
        reply: undefined,
        executionHint: undefined,
        toolCalls: []
      }));
    } catch (error) {
      setAssistantState((state) => ({
        ...state,
        voiceState: "idle",
        error: error instanceof Error ? error.message : "语音输入暂时不可用"
      }));
      await setAudioModeAsync({ allowsRecording: false }).catch(() => undefined);
    }
  }, [assistantState.isLoading, assistantState.voiceState, audioRecorder, stopVoiceRecording]);

  const handleCancelVoiceRecording = useCallback(() => {
    stopVoiceRecording(false).catch(() => undefined);
  }, [stopVoiceRecording]);

  useEffect(() => {
    if (
      assistantState.voiceState === "recording" &&
      !audioRecorderState.isRecording &&
      audioRecorderState.durationMillis >= MAX_VOICE_RECORDING_SECONDS * 1000
    ) {
      stopVoiceRecording(true).catch(() => undefined);
    }
  }, [assistantState.voiceState, audioRecorderState.durationMillis, audioRecorderState.isRecording, stopVoiceRecording]);

  const isExampleVisible = shouldShowExample({
    example: DEFAULT_INTERACTION_EXAMPLE,
    currentTime,
    isStarted: isActive && isStarted,
    dismissed: exampleDismissed,
    presentationType: selectedPresentationType
  });

  return (
    <View style={[styles.root, { height }]}>
      <VideoStage
        isStarted={isStarted}
        isPlaying={canPlay}
        seekRequest={seekRequest}
        onStart={handleStart}
        onTimeChange={handleTimeChange}
        onDurationChange={setMediaDuration}
        showStartEntry={playbackMode.shouldShowStartEntry}
        streamUrl={video.streamUrl}
      />
      {isActive && isStarted && danmakuState === "ready" ? (
        <DanmakuLayer currentTime={currentTime} danmaku={danmaku} isPlaying={canPlay} seekVersion={seekVersion} />
      ) : null}
      {isActive && isStarted ? <Pressable style={styles.tapLayer} onPress={handleTogglePlay} /> : null}
      {isActive && danmakuState === "error" ? <Text style={styles.danmakuError}>弹幕暂不可用</Text> : null}
      <PlaybackHint isStarted={isStarted} isPlaying={canPlay} />
      <InteractionExampleRenderer
        example={DEFAULT_INTERACTION_EXAMPLE}
        presentationType={selectedPresentationType}
        visible={isExampleVisible}
        onDismiss={handleDismissExample}
      />
      <PlayerChrome
        onToggleDebug={() => undefined}
        onOpenWatchAssistant={() => setAssistantState((state) => ({ ...state, isOpen: true }))}
        seriesName={video.seriesName}
        title={video.title}
        episodeLabel={video.episodeLabel}
      />
      {ENABLE_INTERACTION_LAB && isActive ? (
        <InteractionLabControls selectedType={selectedPresentationType} onChange={onChangePresentationType} />
      ) : null}
      <PlayerControls currentTime={currentTime} duration={effectiveDuration} onSeekCommit={handleSeekCommit} />
      <WatchAssistantPanel
        visible={assistantState.isOpen}
        message={assistantState.message}
        reply={assistantState.reply}
        error={assistantState.error}
        isLoading={assistantState.isLoading}
        voiceState={assistantState.voiceState}
        voiceDurationSec={Math.min(MAX_VOICE_RECORDING_SECONDS, Math.round(audioRecorderState.durationMillis / 1000))}
        toolCalls={assistantState.toolCalls}
        executionHint={assistantState.executionHint}
        onChangeMessage={(message) => setAssistantState((state) => ({ ...state, message }))}
        onSubmit={handleSubmitWatchAssistant}
        onToggleVoiceRecording={handleToggleVoiceRecording}
        onCancelVoiceRecording={handleCancelVoiceRecording}
        onClose={() => setAssistantState((state) => ({ ...state, isOpen: false }))}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    backgroundColor: "#050505",
    overflow: "hidden"
  },
  tapLayer: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 1
  },
  danmakuError: {
    position: "absolute",
    top: 92,
    alignSelf: "center",
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    backgroundColor: "rgba(0,0,0,0.36)",
    borderRadius: 6
  }
});
