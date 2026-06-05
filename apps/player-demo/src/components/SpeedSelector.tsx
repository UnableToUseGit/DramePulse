import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, playerOverlay, radii, spacing } from "../theme";

export const PLAYBACK_RATES = [1, 2] as const;
export type PlaybackRate = (typeof PLAYBACK_RATES)[number];

function formatRate(rate: number) {
  return `${rate}x`;
}

export function SpeedSelector({
  selectedRate,
  isOpen,
  onToggle,
  onSelect
}: {
  selectedRate: PlaybackRate;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (rate: PlaybackRate) => void;
}) {
  return (
    <View style={styles.root}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="选择播放倍速"
        style={[styles.button, isOpen ? styles.buttonOpen : null]}
        onPress={onToggle}
      >
        <Text style={styles.buttonText}>{formatRate(selectedRate)}</Text>
        <Ionicons name={isOpen ? "chevron-up" : "chevron-down"} size={13} color={colors.text} />
      </Pressable>

      {isOpen ? (
        <View style={styles.menu}>
          {PLAYBACK_RATES.map((rate) => {
            const selected = selectedRate === rate;
            return (
              <Pressable
                key={rate}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                style={[styles.option, selected ? styles.optionSelected : null]}
                onPress={() => onSelect(rate)}
              >
                <Text style={[styles.optionText, selected ? styles.optionTextSelected : null]}>
                  {formatRate(rate)}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "relative",
    zIndex: 30
  },
  button: {
    minWidth: 56,
    height: playerOverlay.topButtonHeight,
    paddingHorizontal: 11,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 3,
    borderRadius: radii.pill,
    backgroundColor: "rgba(0,0,0,0.46)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.13)"
  },
  buttonOpen: {
    borderColor: "rgba(255,213,138,0.74)"
  },
  buttonText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "900",
    ...playerOverlay.textShadow
  },
  menu: {
    position: "absolute",
    top: 40,
    right: 0,
    width: 72,
    padding: spacing.xs,
    borderRadius: radii.small,
    backgroundColor: "rgba(0,0,0,0.74)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.16)"
  },
  option: {
    alignItems: "center",
    paddingVertical: 7,
    borderRadius: radii.small
  },
  optionSelected: {
    backgroundColor: "rgba(255,106,26,0.9)"
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
