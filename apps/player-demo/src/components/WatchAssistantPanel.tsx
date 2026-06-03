import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { WatchAssistantToolCall } from "../domain/watchAssistant";
import { colors, radii, spacing } from "../theme";

const QUICK_COMMANDS = ["刚才发生了什么", "快进到高光", "下一集", "暂停"];

export function WatchAssistantPanel({
  visible,
  message,
  reply,
  error,
  isLoading,
  voiceState,
  voiceDurationSec,
  toolCalls,
  executionHint,
  onChangeMessage,
  onSubmit,
  onToggleVoiceRecording,
  onCancelVoiceRecording,
  onClose
}: {
  visible: boolean;
  message: string;
  reply?: string;
  error?: string;
  isLoading: boolean;
  voiceState: "idle" | "recording" | "transcribing";
  voiceDurationSec: number;
  toolCalls: WatchAssistantToolCall[];
  executionHint?: string;
  onChangeMessage: (value: string) => void;
  onSubmit: (message?: string) => void;
  onToggleVoiceRecording: () => void;
  onCancelVoiceRecording: () => void;
  onClose: () => void;
}) {
  if (!visible) {
    return null;
  }

  return (
    <View style={styles.root}>
      <View style={styles.handle} />
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <MaterialCommunityIcons name="robot-outline" size={22} color={colors.gold} />
          <Text style={styles.title}>观看助手</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="关闭观看助手" style={styles.closeButton} onPress={onClose}>
          <Ionicons name="close" size={22} color={colors.text} />
        </Pressable>
      </View>

      <View style={styles.quickList}>
        {QUICK_COMMANDS.map((item) => (
          <Pressable key={item} style={styles.quickButton} onPress={() => onSubmit(item)} disabled={isLoading}>
            <Text style={styles.quickText}>{item}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.inputRow}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={voiceState === "recording" ? "结束语音输入" : "开始语音输入"}
          style={[
            styles.voiceButton,
            voiceState === "recording" ? styles.voiceButtonActive : null,
            voiceState === "transcribing" || isLoading ? styles.voiceButtonDisabled : null
          ]}
          onPress={onToggleVoiceRecording}
          disabled={voiceState === "transcribing" || isLoading}
        >
          <Ionicons name={voiceState === "recording" ? "stop" : "mic"} size={19} color={colors.text} />
        </Pressable>
        <TextInput
          value={message}
          onChangeText={onChangeMessage}
          placeholder="问剧情，或说快进、暂停、下一集"
          placeholderTextColor="rgba(255,255,255,0.44)"
          style={styles.input}
          multiline
          maxLength={100}
          editable={!isLoading}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="发送观看助手指令"
          style={[styles.sendButton, isLoading ? styles.sendButtonDisabled : null]}
          onPress={() => onSubmit()}
          disabled={isLoading || voiceState !== "idle"}
        >
          <Ionicons name="send" size={18} color={colors.text} />
        </Pressable>
      </View>

      {voiceState !== "idle" ? (
        <View style={styles.voiceStatusRow}>
          <View style={styles.voicePulse} />
          <Text style={styles.voiceStatusText}>
            {voiceState === "recording" ? `正在听 ${voiceDurationSec}s` : "正在转写语音..."}
          </Text>
          {voiceState === "recording" ? (
            <Pressable accessibilityRole="button" accessibilityLabel="取消语音输入" onPress={onCancelVoiceRecording}>
              <Text style={styles.cancelVoiceText}>取消</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}

      <View style={styles.answerBox}>
        {isLoading ? <Text style={styles.answerText}>正在理解指令...</Text> : null}
        {!isLoading && reply ? <Text style={styles.answerText}>{reply}</Text> : null}
        {!isLoading && executionHint ? <Text style={styles.hintText}>{executionHint}</Text> : null}
        {!isLoading && error ? <Text style={styles.errorText}>{error}</Text> : null}
        {!isLoading && !reply && !error ? <Text style={styles.emptyText}>可以问剧情，也可以控制播放。</Text> : null}
      </View>

      {toolCalls.length > 0 ? (
        <View style={styles.toolRow}>
          {toolCalls.slice(0, 3).map((call, index) => (
            <Text key={`${call.tool}-${index}`} style={[styles.toolChip, call.status === "error" ? styles.toolChipError : null]}>
              {call.tool}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    minHeight: 330,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: 88,
    backgroundColor: "rgba(8,8,10,0.95)",
    borderTopLeftRadius: radii.panel,
    borderTopRightRadius: radii.panel,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)",
    zIndex: 20
  },
  handle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: "rgba(255,255,255,0.28)"
  },
  header: {
    marginTop: spacing.md,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.md
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm
  },
  title: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900"
  },
  closeButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 18,
    backgroundColor: "rgba(255,255,255,0.12)"
  },
  quickList: {
    marginTop: spacing.md,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  quickButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    backgroundColor: "rgba(255,255,255,0.12)"
  },
  quickText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "800"
  },
  inputRow: {
    marginTop: spacing.md,
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm
  },
  input: {
    flex: 1,
    minHeight: 46,
    maxHeight: 84,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.small,
    color: colors.text,
    backgroundColor: "rgba(255,255,255,0.1)",
    fontSize: 15,
    fontWeight: "700"
  },
  sendButton: {
    width: 46,
    height: 46,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 23,
    backgroundColor: colors.accent
  },
  sendButtonDisabled: {
    opacity: 0.58
  },
  voiceButton: {
    width: 46,
    height: 46,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 23,
    backgroundColor: "rgba(255,255,255,0.14)"
  },
  voiceButtonActive: {
    backgroundColor: colors.accent
  },
  voiceButtonDisabled: {
    opacity: 0.5
  },
  voiceStatusRow: {
    marginTop: spacing.sm,
    minHeight: 28,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm
  },
  voicePulse: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.gold
  },
  voiceStatusText: {
    flex: 1,
    color: colors.muted,
    fontSize: 13,
    fontWeight: "800"
  },
  cancelVoiceText: {
    color: colors.gold,
    fontSize: 13,
    fontWeight: "900"
  },
  answerBox: {
    marginTop: spacing.md,
    minHeight: 74,
    padding: spacing.md,
    borderRadius: radii.small,
    backgroundColor: "rgba(255,255,255,0.08)"
  },
  answerText: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
    fontWeight: "700"
  },
  hintText: {
    marginTop: spacing.xs,
    color: colors.gold,
    fontSize: 13,
    lineHeight: 19,
    fontWeight: "800"
  },
  errorText: {
    color: colors.gold,
    fontSize: 14,
    lineHeight: 21,
    fontWeight: "800"
  },
  emptyText: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 21,
    fontWeight: "700"
  },
  toolRow: {
    marginTop: spacing.sm,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  toolChip: {
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.small,
    color: colors.muted,
    backgroundColor: "rgba(255,255,255,0.1)",
    fontSize: 11,
    fontWeight: "800"
  },
  toolChipError: {
    color: colors.gold
  }
});
