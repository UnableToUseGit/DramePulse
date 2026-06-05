import { StyleSheet, View } from "react-native";
import { InnerVoiceDanmakuExample } from "../inner-voice-danmaku/InnerVoiceDanmakuExample";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
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
        <View pointerEvents="box-none" style={styles.innerVoiceSlot}>
          <InnerVoiceDanmakuExample
            currentTime={currentTime}
            isActive={isActive}
            showImmediately
            onDismiss={() => undefined}
            onGestureActiveChange={onInnerVoiceGestureActiveChange}
            onSend={onSendInnerVoiceDanmaku}
          />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    width: 34,
    height: 34,
    marginBottom: 12,
    overflow: "visible",
    zIndex: 12
  },
  innerVoiceSlot: {
    position: "absolute",
    left: 42,
    top: 0,
    width: 220,
    height: 36,
    justifyContent: "center",
    alignItems: "flex-start"
  }
});
