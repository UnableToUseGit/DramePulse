import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";
import { radii, spacing } from "../theme";

export function DanmakuEntryButton() {
  return (
    <View pointerEvents="none" style={styles.root}>
      <Ionicons name="chatbubble-ellipses" size={15} color="rgba(255,255,255,0.84)" />
      <Text style={styles.text}>弹幕</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    alignSelf: "flex-start",
    height: 32,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: "rgba(0,0,0,0.46)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.13)"
  },
  text: {
    color: "rgba(255,255,255,0.78)",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0
  }
});
