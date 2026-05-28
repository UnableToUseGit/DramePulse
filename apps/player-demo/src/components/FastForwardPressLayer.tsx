import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

export function FastForwardPressLayer({
  isHoldingFastForward,
  onPress,
  onLongPress,
  onPressOut
}: {
  isHoldingFastForward: boolean;
  onPress: () => void;
  onLongPress: () => void;
  onPressOut: () => void;
}) {
  return (
    <Pressable
      style={styles.root}
      delayLongPress={260}
      onPress={onPress}
      onLongPress={onLongPress}
      onPressOut={onPressOut}
    >
      {isHoldingFastForward ? (
        <View style={styles.hint}>
          <Text style={styles.hintText}>2x</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    top: 96,
    right: 0,
    bottom: 120,
    width: "42%",
    alignItems: "center",
    justifyContent: "center"
  },
  hint: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 999,
    backgroundColor: "rgba(0,0,0,0.56)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)"
  },
  hintText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900"
  }
});
