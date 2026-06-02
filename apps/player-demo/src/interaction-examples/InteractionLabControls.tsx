import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";
import { getPresentationLabel } from "./trigger";
import type { InteractionPresentationType } from "./types";

const OPTIONS: InteractionPresentationType[] = [
  "none",
  "poll_bar",
  "danmaku_poll",
  "emoji_hold",
  "emotion_aura",
  "inner_voice_danmaku",
  "action_rail_resonance"
];

export function InteractionLabControls({
  selectedType,
  onChange
}: {
  selectedType: InteractionPresentationType;
  onChange: (type: InteractionPresentationType) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);

  const handleChange = (type: InteractionPresentationType) => {
    onChange(type);
    setIsOpen(false);
  };

  return (
    <View style={styles.root} pointerEvents="box-none">
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Open interaction lab"
        style={[styles.menuButton, isOpen ? styles.menuButtonOpen : null]}
        onPress={() => setIsOpen((open) => !open)}
      >
        <Ionicons name={isOpen ? "close" : "menu"} size={25} color={colors.text} />
      </Pressable>

      {isOpen ? (
        <View style={styles.panel}>
          <Text style={styles.title}>Interaction Lab</Text>
          <View style={styles.options}>
            {OPTIONS.map((type) => {
              const selected = selectedType === type;
              return (
                <Pressable
                  key={type}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  style={[styles.option, selected ? styles.optionSelected : null]}
                  onPress={() => handleChange(type)}
                >
                  <Text style={[styles.optionText, selected ? styles.optionTextSelected : null]}>
                    {getPresentationLabel(type)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    top: 92,
    left: spacing.lg,
    alignItems: "flex-start",
    zIndex: 20
  },
  menuButton: {
    width: 42,
    height: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 21,
    backgroundColor: "rgba(0,0,0,0.42)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.14)"
  },
  menuButtonOpen: {
    backgroundColor: "rgba(255,106,26,0.86)",
    borderColor: "rgba(255,213,138,0.78)"
  },
  panel: {
    width: 188,
    marginTop: spacing.sm,
    padding: 7,
    borderRadius: radii.panel,
    backgroundColor: "rgba(0, 0, 0, 0.72)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.16)"
  },
  title: {
    marginBottom: spacing.xs,
    color: colors.muted,
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 0,
    textAlign: "center",
    textTransform: "uppercase"
  },
  options: {
    gap: 5
  },
  option: {
    alignItems: "flex-start",
    paddingHorizontal: spacing.md,
    paddingVertical: 7,
    borderRadius: radii.small,
    backgroundColor: "rgba(255,255,255,0.08)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)"
  },
  optionSelected: {
    backgroundColor: "rgba(255,106,26,0.9)",
    borderColor: "rgba(255,213,138,0.9)"
  },
  optionText: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "900"
  },
  optionTextSelected: {
    color: colors.text
  }
});
