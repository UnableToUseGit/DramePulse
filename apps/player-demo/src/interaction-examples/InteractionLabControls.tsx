import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";
import { getPresentationLabel } from "./trigger";
import type { InteractionPresentationType } from "./types";

const OPTIONS: InteractionPresentationType[] = ["none", "poll_bar", "emoji_hold"];

export function InteractionLabControls({
  selectedType,
  onChange
}: {
  selectedType: InteractionPresentationType;
  onChange: (type: InteractionPresentationType) => void;
}) {
  return (
    <View style={styles.root} pointerEvents="box-none">
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
                onPress={() => onChange(type)}
              >
                <Text style={[styles.optionText, selected ? styles.optionTextSelected : null]}>
                  {getPresentationLabel(type)}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    top: spacing.lg,
    left: spacing.lg,
    right: spacing.lg,
    alignItems: "center"
  },
  panel: {
    maxWidth: "100%",
    padding: spacing.xs,
    borderRadius: radii.panel,
    backgroundColor: "rgba(0, 0, 0, 0.48)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.14)"
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
    flexDirection: "row",
    gap: spacing.xs
  },
  option: {
    minWidth: 64,
    alignItems: "center",
    paddingHorizontal: spacing.sm,
    paddingVertical: 7,
    borderRadius: radii.pill,
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
    fontSize: 11,
    fontWeight: "900"
  },
  optionTextSelected: {
    color: colors.text
  }
});
