import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text } from "react-native";
import { colors } from "../theme";

export function FloatingStoryQaButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel="打开剧情问答" style={styles.root} onPress={onPress}>
      <Ionicons name="chatbubble-ellipses" size={22} color={colors.text} />
      <Text style={styles.label}>问</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    right: 16,
    top: "42%",
    width: 58,
    height: 58,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 29,
    backgroundColor: "rgba(255, 106, 26, 0.88)",
    borderWidth: 1,
    borderColor: "rgba(255, 213, 138, 0.76)",
    shadowColor: "#000",
    shadowOpacity: 0.28,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
    zIndex: 16
  },
  label: {
    marginTop: -2,
    color: colors.text,
    fontSize: 11,
    fontWeight: "900"
  }
});
