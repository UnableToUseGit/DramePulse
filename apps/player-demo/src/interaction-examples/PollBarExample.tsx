import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";
import type { InteractionExample, InteractionReaction } from "./types";

export function PollBarExample({ example, onDismiss }: { example: InteractionExample; onDismiss: () => void }) {
  const [selectedReaction, setSelectedReaction] = useState<InteractionReaction | undefined>();

  useEffect(() => {
    setSelectedReaction(undefined);
  }, [example.id]);

  useEffect(() => {
    if (!selectedReaction) {
      return;
    }
    const timer = setTimeout(onDismiss, 1800);
    return () => clearTimeout(timer);
  }, [onDismiss, selectedReaction]);

  return (
    <View style={styles.root} pointerEvents="box-none">
      <View style={[styles.bar, selectedReaction ? styles.resultBar : null]}>
        {selectedReaction ? (
          <Text style={styles.resultText}>
            {selectedReaction.emoji} 已收到，你和很多观众都觉得「{selectedReaction.label}」
          </Text>
        ) : (
          <>
            <Text style={styles.question}>{example.prompt}</Text>
            <View style={styles.options}>
              {example.reactions.map((reaction) => (
                <Pressable key={reaction.id} style={styles.option} onPress={() => setSelectedReaction(reaction)}>
                  <Text style={styles.optionEmoji}>{reaction.emoji}</Text>
                  <Text style={styles.optionText}>{reaction.label}</Text>
                </Pressable>
              ))}
            </View>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    top: "42%",
    alignItems: "center"
  },
  bar: {
    maxWidth: "100%",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.panel,
    backgroundColor: colors.panel,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.35,
    shadowRadius: 18
  },
  resultBar: {
    borderColor: "rgba(255,106,26,0.76)",
    backgroundColor: "rgba(28, 12, 5, 0.9)"
  },
  question: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "900",
    textAlign: "center"
  },
  options: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: spacing.sm,
    marginTop: spacing.sm
  },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radii.pill,
    backgroundColor: "rgba(255,255,255,0.13)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)"
  },
  optionEmoji: {
    fontSize: 15
  },
  optionText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900"
  },
  resultText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "900",
    textAlign: "center"
  }
});
