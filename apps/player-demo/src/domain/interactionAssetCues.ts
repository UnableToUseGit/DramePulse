import type { ActionRailResonanceCue, ActionRailResonanceEmotionType } from "../action-rail-resonance/types";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
import type { InteractionAsset } from "./playerDataApi";

type TimedInteractionCue = {
  cueId: string;
  triggerTime: number;
  durationSec: number;
};

export type InteractionDebugMarker = {
  markerId: string;
  time: number;
  mode: "emotional_button" | "inner_voice_danmaku";
};

const EMOTION_BUTTON_COPY: Record<
  ActionRailResonanceEmotionType,
  Pick<ActionRailResonanceCue, "label" | "icon" | "feedbackText">
> = {
  爽点: { label: "爽到了", icon: "flame", feedbackText: "你也爽到了" },
  笑点: { label: "笑到了", icon: "happy", feedbackText: "笑到了" },
  甜点: { label: "甜到了", icon: "gift", feedbackText: "甜到了" },
  泪点: { label: "破防了", icon: "water", feedbackText: "你也破防了" }
};

const DEFAULT_EMOTION_BUTTON_COUNTS: Record<ActionRailResonanceEmotionType, number> = {
  爽点: 82000,
  笑点: 94000,
  甜点: 126000,
  泪点: 34000
};

function toStringContent(value: unknown) {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function toPositiveNumber(value: unknown): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

function resolveBaseCount(asset: InteractionAsset, emotionType: ActionRailResonanceEmotionType) {
  return (
    toPositiveNumber(asset.content?.base_count) ??
    toPositiveNumber(asset.content?.baseCount) ??
    toPositiveNumber(asset.content?.count) ??
    DEFAULT_EMOTION_BUTTON_COUNTS[emotionType]
  );
}

function resolveDurationSec(asset: InteractionAsset) {
  if (asset.expireTime !== undefined && asset.expireTime > asset.triggerTime) {
    return asset.expireTime - asset.triggerTime;
  }
  return asset.durationSec && asset.durationSec > 0 ? asset.durationSec : 6;
}

function toEmotionType(value: unknown): ActionRailResonanceEmotionType | undefined {
  if (value === "爽点" || value === "笑点" || value === "甜点" || value === "泪点") {
    return value;
  }
  return undefined;
}

export function toActionRailResonanceCues(assets: InteractionAsset[]): ActionRailResonanceCue[] {
  return assets
    .filter((asset) => asset.status !== "inactive" && asset.interactionMode === "emotional_button")
    .map((asset) => {
      const emotionType = toEmotionType(asset.content?.expression_type) ?? "爽点";
      const copy = EMOTION_BUTTON_COPY[emotionType];
      return {
        cueId: asset.interactionId,
        videoId: asset.videoId ?? "",
        highlightId: asset.sourceAssetId ?? asset.interactionId,
        triggerTime: asset.triggerTime,
        durationSec: resolveDurationSec(asset),
        emotionType,
        label: copy.label,
        icon: copy.icon,
        baseCount: resolveBaseCount(asset, emotionType),
        feedbackText: copy.feedbackText
      };
    })
    .sort((a, b) => a.triggerTime - b.triggerTime);
}

export function toInnerVoiceDanmakuCues(assets: InteractionAsset[]): InnerVoiceDanmakuCue[] {
  return assets
    .filter((asset) => asset.status !== "inactive" && asset.interactionMode === "inner_voice_danmaku")
    .map((asset) => {
      const text = toStringContent(asset.content?.text);
      if (!text) {
        return undefined;
      }
      return {
        cueId: asset.interactionId,
        videoId: asset.videoId ?? "",
        highlightId: asset.sourceAssetId ?? asset.interactionId,
        triggerTime: asset.triggerTime,
        durationSec: resolveDurationSec(asset),
        text
      };
    })
    .filter((cue): cue is InnerVoiceDanmakuCue => cue !== undefined)
    .sort((a, b) => a.triggerTime - b.triggerTime);
}

export function getExpiredInteractionCueIds({
  cues,
  currentTime,
  completedCueIds
}: {
  cues: TimedInteractionCue[];
  currentTime: number;
  completedCueIds: Set<string>;
}) {
  return cues
    .filter((cue) => !completedCueIds.has(cue.cueId) && currentTime > cue.triggerTime + cue.durationSec)
    .map((cue) => cue.cueId);
}

export function getSeekSkippedInteractionCueIds({
  cues,
  seekTime,
  completedCueIds
}: {
  cues: TimedInteractionCue[];
  seekTime: number;
  completedCueIds: Set<string>;
}) {
  return cues
    .filter(
      (cue) =>
        !completedCueIds.has(cue.cueId) &&
        seekTime >= cue.triggerTime &&
        seekTime <= cue.triggerTime + cue.durationSec
    )
    .map((cue) => cue.cueId);
}

export function toInteractionDebugMarkers(assets: InteractionAsset[]): InteractionDebugMarker[] {
  return assets
    .filter(
      (asset) =>
        asset.status !== "inactive" &&
        (asset.interactionMode === "emotional_button" || asset.interactionMode === "inner_voice_danmaku")
    )
    .map((asset) => ({
      markerId: asset.interactionId,
      time: asset.triggerTime,
      mode: asset.interactionMode as InteractionDebugMarker["mode"]
    }))
    .sort((a, b) => a.time - b.time);
}
