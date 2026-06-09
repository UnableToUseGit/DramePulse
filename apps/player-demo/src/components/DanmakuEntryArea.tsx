import { StyleSheet, View } from "react-native";
import { InnerVoiceDanmakuExample } from "../inner-voice-danmaku/InnerVoiceDanmakuExample";
import { InnerVoicePrompt } from "../inner-voice-danmaku/InnerVoicePrompt";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
import { DanmakuEntryButton } from "./DanmakuEntryButton";

export function DanmakuEntryArea({
  currentTime,
  isActive,
  showInnerVoice,
  innerVoiceCue,
  showInnerVoiceExample = false,
  onInnerVoiceGestureActiveChange,
  onSendInnerVoiceDanmaku,
  onInnerVoiceExitComplete
}: {
  currentTime: number;
  isActive: boolean;
  showInnerVoice: boolean;
  innerVoiceCue?: InnerVoiceDanmakuCue;
  showInnerVoiceExample?: boolean;
  onInnerVoiceGestureActiveChange: (active: boolean) => void;
  onSendInnerVoiceDanmaku: (cue: InnerVoiceDanmakuCue) => void;
  onInnerVoiceExitComplete: (cue: InnerVoiceDanmakuCue) => void;
}) {
  return (
    <View pointerEvents="box-none" style={styles.root}>
      <DanmakuEntryButton />
      {innerVoiceCue ? (
        <View pointerEvents="box-none" style={styles.innerVoiceSlot}>
          <InnerVoicePrompt
            key={innerVoiceCue.cueId}
            cue={innerVoiceCue}
            onGestureActiveChange={onInnerVoiceGestureActiveChange}
            onSend={onSendInnerVoiceDanmaku}
            onExitComplete={onInnerVoiceExitComplete}
          />
        </View>
      ) : null}
      {!innerVoiceCue && showInnerVoice && showInnerVoiceExample ? (
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
    width: 74,
    height: 34,
    overflow: "visible",
    zIndex: 12
  },
  innerVoiceSlot: {
    position: "absolute",
    left: 42,
    top: -1,
    width: 220,
    height: 36,
    justifyContent: "center",
    alignItems: "flex-start"
  }
});
