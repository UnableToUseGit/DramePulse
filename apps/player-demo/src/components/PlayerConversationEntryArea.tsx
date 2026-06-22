import { StyleSheet, View } from "react-native";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
import { DanmakuEntryArea } from "./DanmakuEntryArea";
import { WatchAssistantEntry } from "./WatchAssistantEntry";

export function PlayerConversationEntryArea({
  currentTime,
  isActive,
  showInnerVoice,
  innerVoiceCue,
  showInnerVoiceExample = false,
  onOpenWatchAssistant,
  onInnerVoiceGestureActiveChange,
  onSendInnerVoiceDanmaku,
  onInnerVoiceExitComplete
}: {
  currentTime: number;
  isActive: boolean;
  showInnerVoice: boolean;
  innerVoiceCue?: InnerVoiceDanmakuCue;
  showInnerVoiceExample?: boolean;
  onOpenWatchAssistant: () => void;
  onInnerVoiceGestureActiveChange: (active: boolean) => void;
  onSendInnerVoiceDanmaku: (cue: InnerVoiceDanmakuCue) => void;
  onInnerVoiceExitComplete: (cue: InnerVoiceDanmakuCue) => void;
}) {
  return (
    <View pointerEvents="box-none" style={styles.root}>
      <WatchAssistantEntry onPress={onOpenWatchAssistant} />
      <DanmakuEntryArea
        currentTime={currentTime}
        isActive={isActive}
        showInnerVoice={showInnerVoice}
        innerVoiceCue={innerVoiceCue}
        showInnerVoiceExample={showInnerVoiceExample}
        onInnerVoiceGestureActiveChange={onInnerVoiceGestureActiveChange}
        onSendInnerVoiceDanmaku={onSendInnerVoiceDanmaku}
        onInnerVoiceExitComplete={onInnerVoiceExitComplete}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    width: 84,
    height: 34,
    marginBottom: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    overflow: "visible",
    zIndex: 12
  }
});
