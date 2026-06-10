import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Animated, PanResponder, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { WatchAssistantToolCall } from "../domain/watchAssistant";
import { colors, radii, spacing } from "../theme";

const QUICK_COMMANDS = ["刚才发生了什么", "快进到高光", "下一集", "暂停"];
const PANEL_HIDDEN_TRANSLATE_Y = 380;
const SWIPE_DISMISS_DISTANCE_PX = 72;

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
  onInteractionBlockChange,
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
  onInteractionBlockChange?: (isBlocked: boolean) => void;
  onClose: () => void;
}) {
  const [shouldRender, setShouldRender] = useState(visible);
  const sheetProgress = useRef(new Animated.Value(visible ? 1 : 0)).current;
  const dragTranslateY = useRef(new Animated.Value(0)).current;
  const isAnimatingRef = useRef(false);

  useEffect(() => {
    if (visible) {
      setShouldRender(true);
      dragTranslateY.setValue(0);
      isAnimatingRef.current = true;
      Animated.parallel([
        Animated.timing(sheetProgress, {
          toValue: 1,
          duration: 240,
          useNativeDriver: true
        }),
        Animated.spring(dragTranslateY, {
          toValue: 0,
          tension: 72,
          friction: 12,
          useNativeDriver: true
        })
      ]).start(() => {
        isAnimatingRef.current = false;
      });
      return;
    }

    if (!shouldRender) {
      return;
    }

    isAnimatingRef.current = true;
    Animated.parallel([
      Animated.timing(sheetProgress, {
        toValue: 0,
        duration: 220,
        useNativeDriver: true
      }),
      Animated.timing(dragTranslateY, {
        toValue: 0,
        duration: 220,
        useNativeDriver: true
      })
    ]).start(() => {
      isAnimatingRef.current = false;
      setShouldRender(false);
    });
  }, [dragTranslateY, sheetProgress, shouldRender, visible]);

  useEffect(() => {
    onInteractionBlockChange?.(shouldRender);
    return () => {
      onInteractionBlockChange?.(false);
    };
  }, [onInteractionBlockChange, shouldRender]);

  const requestClose = () => {
    if (!visible || isAnimatingRef.current) {
      return;
    }
    onClose();
  };

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponderCapture: (_event, gesture) =>
          gesture.dy > 8 && Math.abs(gesture.dy) > Math.abs(gesture.dx),
        onPanResponderMove: (_event, gesture) => {
          dragTranslateY.setValue(Math.max(0, gesture.dy));
        },
        onPanResponderRelease: (_event, gesture) => {
          if (gesture.dy > SWIPE_DISMISS_DISTANCE_PX) {
            requestClose();
            return;
          }
          Animated.spring(dragTranslateY, {
            toValue: 0,
            tension: 84,
            friction: 11,
            useNativeDriver: true
          }).start();
        },
        onPanResponderTerminate: () => {
          Animated.spring(dragTranslateY, {
            toValue: 0,
            tension: 84,
            friction: 11,
            useNativeDriver: true
          }).start();
        }
      }),
    [dragTranslateY, visible]
  );

  if (!shouldRender) {
    return null;
  }

  const overlayOpacity = sheetProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 1]
  });
  const primaryAnswer = reply?.trim() || executionHint?.trim();
  const translateY = Animated.add(
    dragTranslateY,
    sheetProgress.interpolate({
      inputRange: [0, 1],
      outputRange: [PANEL_HIDDEN_TRANSLATE_Y, 0]
    })
  );

  return (
    <View pointerEvents="box-none" style={styles.overlay}>
      <Animated.View style={[styles.backdropWrap, { opacity: overlayOpacity }]}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="关闭观看助手遮罩"
          style={styles.backdrop}
          onPress={requestClose}
        />
      </Animated.View>
      <Animated.View style={[styles.root, { transform: [{ translateY }] }]}>
        <View style={styles.handleTouchArea} {...panResponder.panHandlers}>
          <View style={styles.handle} />
        </View>
        <View style={styles.header}>
          <View style={styles.titleRow}>
            <MaterialCommunityIcons name="robot-outline" size={18} color="#8A6A2F" />
            <Text style={styles.title}>陪看助手</Text>
          </View>
        </View>
        <View style={styles.contentSection}>
          <View style={styles.answerBox}>
            {isLoading ? (
              <View style={styles.loadingRow}>
                <ActivityIndicator size="small" color={colors.accent} />
                <Text style={styles.loadingText}>处理中</Text>
              </View>
            ) : null}
            {!isLoading && primaryAnswer ? <Text style={styles.answerText}>{primaryAnswer}</Text> : null}
            {!isLoading && error ? <Text style={styles.errorText}>{error}</Text> : null}
            {!isLoading && !primaryAnswer && !error ? (
              <Text style={styles.emptyText}>要我帮你捋一捋这段剧情吗</Text>
            ) : null}
          </View>
        </View>

        <View style={styles.composerSection}>
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
              <Ionicons name={voiceState === "recording" ? "stop" : "mic"} size={21} color="#222222" />
            </Pressable>
            <TextInput
              value={message}
              onChangeText={onChangeMessage}
              placeholder="问剧情，或说快进、暂停、下一集"
              placeholderTextColor="rgba(34,34,34,0.42)"
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
              <Ionicons name="send" size={18} color="#FFFFFF" />
            </Pressable>
          </View>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 20
  },
  backdropWrap: {
    ...StyleSheet.absoluteFillObject
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.18)"
  },
  root: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    minHeight: 316,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: 52,
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: radii.panel,
    borderTopRightRadius: radii.panel,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.72)",
    shadowColor: "rgba(0,0,0,0.18)",
    shadowOffset: { width: 0, height: -6 },
    shadowOpacity: 1,
    shadowRadius: 20,
    zIndex: 21
  },
  handleTouchArea: {
    alignSelf: "stretch",
    alignItems: "center",
    justifyContent: "center",
    height: 28,
    marginTop: -4
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: "rgba(28,28,30,0.18)"
  },
  header: {
    marginTop: spacing.xs,
    alignItems: "center",
    justifyContent: "center"
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xs
  },
  title: {
    color: "#3A3A3A",
    fontSize: 17,
    fontWeight: "700"
  },
  contentSection: {
    flex: 1,
    justifyContent: "center",
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm
  },
  composerSection: {
    marginTop: spacing.lg,
    paddingTop: spacing.sm,
    gap: spacing.sm
  },
  quickList: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  quickButton: {
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: radii.pill,
    backgroundColor: "#F3F4F6",
    borderWidth: 1,
    borderColor: "#E5E7EB"
  },
  quickText: {
    color: "#424242",
    fontSize: 13,
    fontWeight: "700"
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm
  },
  input: {
    flex: 1,
    minHeight: 48,
    maxHeight: 88,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    borderRadius: 16,
    color: "#191919",
    backgroundColor: "#F8F8F8",
    borderWidth: 1,
    borderColor: "#E8E8E8",
    fontSize: 15,
    fontWeight: "600"
  },
  sendButton: {
    width: 46,
    height: 46,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 23,
    backgroundColor: "#262626"
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
    backgroundColor: "#F3F4F6",
    borderWidth: 1,
    borderColor: "#E5E7EB"
  },
  voiceButtonActive: {
    backgroundColor: colors.accent
  },
  voiceButtonDisabled: {
    opacity: 0.5
  },
  voiceStatusRow: {
    minHeight: 28,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm
  },
  voicePulse: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.accent
  },
  voiceStatusText: {
    flex: 1,
    color: "#6B7280",
    fontSize: 13,
    fontWeight: "700"
  },
  cancelVoiceText: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: "800"
  },
  answerBox: {
    minHeight: 92,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.lg,
    borderRadius: 16,
    backgroundColor: "rgba(255,255,255,0.72)",
    borderWidth: 1,
    borderColor: "rgba(30,41,59,0.08)",
    alignItems: "center",
    justifyContent: "center"
  },
  answerText: {
    color: "#161616",
    fontSize: 16,
    lineHeight: 24,
    fontWeight: "700",
    textAlign: "center"
  },
  loadingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm
  },
  loadingText: {
    color: "#4B5563",
    fontSize: 14,
    lineHeight: 21,
    fontWeight: "700"
  },
  hintText: {
    marginTop: spacing.xs,
    color: colors.accent,
    fontSize: 13,
    lineHeight: 19,
    fontWeight: "700",
    textAlign: "center"
  },
  errorText: {
    color: "#C2410C",
    fontSize: 14,
    lineHeight: 21,
    fontWeight: "700",
    textAlign: "center"
  },
  emptyText: {
    color: "#6B7280",
    fontSize: 14,
    lineHeight: 21,
    fontWeight: "600",
    textAlign: "center"
  },
  toolRow: {
    marginTop: spacing.sm,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    justifyContent: "center"
  },
  toolChip: {
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.small,
    color: "#6B7280",
    backgroundColor: "#F5F5F5",
    fontSize: 11,
    fontWeight: "700"
  },
  toolChipError: {
    color: "#C2410C"
  }
});
