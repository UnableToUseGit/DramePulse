import { EmotionAuraExample } from "../emotion-aura/EmotionAuraExample";
import { DanmakuPollExample } from "./DanmakuPollExample";
import { EmojiHoldExample } from "./EmojiHoldExample";
import { PollBarExample } from "./PollBarExample";
import type { InteractionExample, InteractionPresentationType } from "./types";

export function InteractionExampleRenderer({
  example,
  presentationType,
  visible,
  currentTime,
  isActive,
  onDismiss,
  onTogglePlayback
}: {
  example: InteractionExample;
  presentationType: InteractionPresentationType;
  visible: boolean;
  currentTime: number;
  isActive: boolean;
  onDismiss: () => void;
  onTogglePlayback: () => void;
}) {
  if (!visible || presentationType === "none") {
    return null;
  }

  if (presentationType === "emotion_aura") {
    return (
      <EmotionAuraExample
        currentTime={currentTime}
        isActive={isActive}
        onDismiss={() => undefined}
        onTogglePlayback={onTogglePlayback}
      />
    );
  }

  if (presentationType === "poll_bar") {
    return <PollBarExample example={example} onDismiss={onDismiss} />;
  }

  if (presentationType === "danmaku_poll") {
    return <DanmakuPollExample example={example} onDismiss={onDismiss} />;
  }

  return <EmojiHoldExample example={example} onDismiss={onDismiss} />;
}
