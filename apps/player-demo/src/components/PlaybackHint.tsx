import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, View } from "react-native";
import { colors, spacing } from "../theme";

export function PlaybackHint({ isStarted, isPlaying }: { isStarted: boolean; isPlaying: boolean }) {
  if (!isStarted || isPlaying) {
    return null;
  }

  return (
    <View pointerEvents="none" style={styles.root}>
      <View style={styles.circle}>
        <Ionicons name="play" size={44} color={colors.text} style={styles.icon} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center"
  },
  circle: {
    width: 86,
    height: 86,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 43,
    backgroundColor: "rgba(0,0,0,0.42)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.16)",
    paddingLeft: spacing.xs
  },
  icon: {
    marginLeft: spacing.xs
  }
});
