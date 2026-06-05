import { StyleSheet, View } from "react-native";
import { InnerVoiceDanmakuExample } from "../inner-voice-danmaku/InnerVoiceDanmakuExample";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
import { spacing } from "../theme";
import { DanmakuEntryButton } from "./DanmakuEntryButton";

export function DanmakuEntryArea({
  currentTime,
  isActive,
  showInnerVoice,
  onInnerVoiceGestureActiveChange,
  onSendInnerVoiceDanmaku
}: {
  currentTime: number;
  isActive: boolean;
  showInnerVoice: boolean;
  onInnerVoiceGestureActiveChange: (active: boolean) => void;
  onSendInnerVoiceDanmaku: (cue: InnerVoiceDanmakuCue) => void;
}) {
  return (
    <View pointerEvents="box-none" style={styles.root}>
      <DanmakuEntryButton />
      {showInnerVoice ? (
        <InnerVoiceDanmakuExample
          currentTime={currentTime}
          isActive={isActive}
          showImmediately
          onDismiss={() => undefined}
          onGestureActiveChange={onInnerVoiceGestureActiveChange}
          onSend={onSendInnerVoiceDanmaku}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: 12,
    overflow: "visible",
    zIndex: 12
  }
});
