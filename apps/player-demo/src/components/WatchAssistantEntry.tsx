import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet } from "react-native";

export function WatchAssistantEntry({ onPress }: { onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="观看助手"
      style={styles.root}
      onPress={onPress}
    >
      <Ionicons name="sparkles" size={18} color="rgba(255,255,255,0.9)" />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    width: 34,
    height: 34,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 17,
    backgroundColor: "rgba(0,0,0,0.46)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.13)"
  }
});
