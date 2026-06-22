import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { colors, radii, spacing } from "../theme";

const QUICK_QUESTIONS = ["他是谁？", "刚才发生了什么？", "这段关系是什么？"];

export function StoryQaPanel({
  visible,
  question,
  answer,
  error,
  isLoading,
  onChangeQuestion,
  onSubmit,
  onClose
}: {
  visible: boolean;
  question: string;
  answer?: string;
  error?: string;
  isLoading: boolean;
  onChangeQuestion: (value: string) => void;
  onSubmit: (question?: string) => void;
  onClose: () => void;
}) {
  if (!visible) {
    return null;
  }

  return (
    <View style={styles.root}>
      <View style={styles.handle} />
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.title}>剧情问答</Text>
          <Text style={styles.subtitle}>基于已构建剧情资料回答，可能不严格防剧透</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="关闭剧情问答" style={styles.closeButton} onPress={onClose}>
          <Ionicons name="close" size={22} color={colors.text} />
        </Pressable>
      </View>

      <View style={styles.quickList}>
        {QUICK_QUESTIONS.map((item) => (
          <Pressable key={item} style={styles.quickButton} onPress={() => onSubmit(item)} disabled={isLoading}>
            <Text style={styles.quickText}>{item}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.inputRow}>
        <TextInput
          value={question}
          onChangeText={onChangeQuestion}
          placeholder="问一句剧情问题"
          placeholderTextColor="rgba(255,255,255,0.44)"
          style={styles.input}
          multiline
          maxLength={80}
          editable={!isLoading}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="发送剧情问题"
          style={[styles.sendButton, isLoading ? styles.sendButtonDisabled : null]}
          onPress={() => onSubmit()}
          disabled={isLoading}
        >
          <Ionicons name="send" size={18} color={colors.text} />
        </Pressable>
      </View>

      <View style={styles.answerBox}>
        {isLoading ? <Text style={styles.answerText}>正在检索剧情资料...</Text> : null}
        {!isLoading && error ? <Text style={styles.errorText}>{error}</Text> : null}
        {!isLoading && !error && answer ? <Text style={styles.answerText}>{answer}</Text> : null}
        {!isLoading && !error && !answer ? <Text style={styles.emptyText}>可以问角色身份、刚才剧情或人物关系。</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    minHeight: 318,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: 88,
    backgroundColor: "rgba(8,8,10,0.94)",
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
    gap: spacing.md
  },
  headerText: {
    flex: 1
  },
  title: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900"
  },
  subtitle: {
    marginTop: spacing.xs,
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700"
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
  answerBox: {
    marginTop: spacing.md,
    minHeight: 72,
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
  }
});
