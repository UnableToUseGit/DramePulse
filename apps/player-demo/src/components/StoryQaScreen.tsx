import { Ionicons } from "@expo/vector-icons";
import { useCallback, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { API_BASE_URL } from "../config";
import type { PlayerVideo } from "../domain/playerApi";
import { askStoryQa, resolveStoryQaContext } from "../domain/storyQa";
import { colors, radii, spacing } from "../theme";

const QUICK_QUESTIONS = ["他是谁？", "刚才发生了什么？", "这段关系是什么？", "后面会怎么发展？"];

function formatTime(seconds: number) {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const restSeconds = safeSeconds % 60;
  return `${minutes}:${String(restSeconds).padStart(2, "0")}`;
}

export function StoryQaScreen({
  video,
  currentTime,
  onClose
}: {
  video: PlayerVideo;
  currentTime: number;
  onClose: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | undefined>();
  const [error, setError] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const requestRef = useRef(0);
  const context = resolveStoryQaContext(video);

  const handleSubmit = useCallback(
    (quickQuestion?: string) => {
      const nextQuestion = (quickQuestion ?? question).trim();
      setQuestion(nextQuestion);
      setAnswer(undefined);
      setError(undefined);
      if (!nextQuestion) {
        setError("请输入问题");
        return;
      }

      const requestId = requestRef.current + 1;
      requestRef.current = requestId;
      setIsLoading(true);
      askStoryQa({
        apiBaseUrl: API_BASE_URL,
        question: nextQuestion,
        seriesId: context.seriesId,
        currentEpisode: context.currentEpisode,
        currentTime
      })
        .then((result) => {
          if (requestRef.current === requestId) {
            setAnswer(result.answer);
          }
        })
        .catch((submitError: unknown) => {
          if (requestRef.current === requestId) {
            setError(submitError instanceof Error ? submitError.message : "剧情问答暂时不可用");
          }
        })
        .finally(() => {
          if (requestRef.current === requestId) {
            setIsLoading(false);
          }
        });
    },
    [context.currentEpisode, context.seriesId, currentTime, question]
  );

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.root}
      keyboardVerticalOffset={Platform.OS === "ios" ? 20 : 0}
    >
      <View style={styles.header}>
        <Pressable accessibilityRole="button" accessibilityLabel="关闭剧情问答" style={styles.iconButton} onPress={onClose}>
          <Ionicons name="chevron-back" size={25} color={colors.text} />
        </Pressable>
        <View style={styles.headerText}>
          <Text style={styles.title}>剧情问答</Text>
          <Text numberOfLines={1} style={styles.subtitle}>
            {video.title} · {video.episodeLabel ?? `第 ${context.currentEpisode} 集`} · {formatTime(currentTime)}
          </Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
        <View style={styles.tipCard}>
          <Ionicons name="sparkles" size={20} color={colors.gold} />
          <Text style={styles.tipText}>可以询问人物身份、前情回顾、关系梳理和当前剧情信息。</Text>
        </View>

        <View style={styles.quickList}>
          {QUICK_QUESTIONS.map((item) => (
            <Pressable key={item} style={styles.quickButton} onPress={() => handleSubmit(item)} disabled={isLoading}>
              <Text style={styles.quickText}>{item}</Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.answerBox}>
          {isLoading ? <Text style={styles.answerText}>正在检索剧情资料...</Text> : null}
          {!isLoading && error ? <Text style={styles.errorText}>{error}</Text> : null}
          {!isLoading && !error && answer ? <Text style={styles.answerText}>{answer}</Text> : null}
          {!isLoading && !error && !answer ? (
            <Text style={styles.emptyText}>点击上方快捷问题，或在底部输入你想问的剧情问题。</Text>
          ) : null}
        </View>
      </ScrollView>

      <View style={styles.inputBar}>
        <TextInput
          value={question}
          onChangeText={setQuestion}
          placeholder="问一句剧情问题"
          placeholderTextColor="rgba(255,255,255,0.44)"
          style={styles.input}
          multiline
          maxLength={100}
          editable={!isLoading}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="发送剧情问题"
          style={[styles.sendButton, isLoading ? styles.sendButtonDisabled : null]}
          onPress={() => handleSubmit()}
          disabled={isLoading}
        >
          <Ionicons name="send" size={18} color={colors.text} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    paddingTop: 48,
    backgroundColor: "#101013",
    zIndex: 50
  },
  header: {
    minHeight: 56,
    paddingHorizontal: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md
  },
  iconButton: {
    width: 42,
    height: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 21,
    backgroundColor: "rgba(255,255,255,0.1)"
  },
  headerText: {
    flex: 1,
    minWidth: 0
  },
  title: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "900"
  },
  subtitle: {
    marginTop: spacing.xs,
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700"
  },
  content: {
    padding: spacing.lg,
    paddingBottom: 122
  },
  tipCard: {
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderRadius: radii.small,
    backgroundColor: "rgba(255,255,255,0.08)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)"
  },
  tipText: {
    flex: 1,
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
    fontWeight: "800"
  },
  quickList: {
    marginTop: spacing.lg,
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
  answerBox: {
    marginTop: spacing.lg,
    minHeight: 180,
    padding: spacing.md,
    borderRadius: radii.small,
    backgroundColor: "rgba(0,0,0,0.26)"
  },
  answerText: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 23,
    fontWeight: "700"
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
  inputBar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    minHeight: 84,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm,
    backgroundColor: "rgba(16,16,19,0.96)",
    borderTopWidth: 1,
    borderTopColor: "rgba(255,255,255,0.1)"
  },
  input: {
    flex: 1,
    minHeight: 46,
    maxHeight: 92,
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
  }
});
