import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";
import type { InteractionExample, InteractionReaction } from "./types";

export function DanmakuPollExample({ example, onDismiss }: { example: InteractionExample; onDismiss: () => void }) {
  const [selectedReaction, setSelectedReaction] = useState<InteractionReaction | undefined>();

  useEffect(() => {
    setSelectedReaction(undefined);
  }, [example.id]);

  useEffect(() => {
    if (!selectedReaction) {
      return;
    }
    const timer = setTimeout(onDismiss, 2200);
    return () => clearTimeout(timer);
  }, [onDismiss, selectedReaction]);

  return (
    <View style={styles.root} pointerEvents="box-none">
      <View style={styles.floatLayer} pointerEvents="none">
        {(selectedReaction ? [selectedReaction, ...example.reactions] : example.reactions).slice(0, 4).map((item, index) => (
          <Text
            key={`${item.id}-${index}`}
            style={[
              styles.danmakuText,
              {
                top: index * 34,
                right: 18 + index * 24,
                opacity: selectedReaction ? 1 - index * 0.12 : 0.84
              }
            ]}
          >
            {selectedReaction ? `${item.emoji} ${item.label} +1` : `${item.emoji} ${item.label}`}
          </Text>
        ))}
      </View>

      <View style={[styles.panel, selectedReaction ? styles.resultPanel : null]}>
        {selectedReaction ? (
          <Text style={styles.resultText}>{selectedReaction.emoji} 这条弹幕已发射</Text>
        ) : (
          <>
            <Text style={styles.prompt}>{example.prompt}</Text>
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
    top: "34%",
    alignItems: "center"
  },
  floatLayer: {
    position: "absolute",
    left: 0,
    right: 0,
    top: -118,
    height: 116
  },
  danmakuText: {
    position: "absolute",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    overflow: "hidden",
    color: colors.gold,
    backgroundColor: "rgba(0,0,0,0.48)",
    fontSize: 16,
    fontWeight: "900",
    textShadowColor: colors.accentDeep,
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 8
  },
  panel: {
    maxWidth: "100%",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    backgroundColor: "rgba(8, 8, 10, 0.78)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)"
  },
  resultPanel: {
    borderColor: "rgba(255,213,138,0.82)",
    backgroundColor: "rgba(42, 18, 6, 0.88)"
  },
  prompt: {
    color: colors.text,
    fontSize: 15,
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
    backgroundColor: "rgba(255,255,255,0.12)",
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
