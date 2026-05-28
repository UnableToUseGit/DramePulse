import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

export function LikeReactionButton({
  count,
  liked,
  onToggle
}: {
  count: string;
  liked: boolean;
  onToggle: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={liked ? "取消点赞" : "点赞"}
      accessibilityState={{ selected: liked }}
      style={styles.root}
      onPress={onToggle}
    >
      <View style={styles.iconWrap}>
        <Ionicons name="heart" size={42} color={liked ? "#FF335F" : "#fff"} />
      </View>
      <Text style={styles.railText}>{count}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    alignItems: "center",
    width: 76,
    gap: spacing.xs
  },
  iconWrap: {
    width: 72,
    height: 72,
    alignItems: "center",
    justifyContent: "center"
  },
  railText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    textShadowColor: "rgba(0,0,0,0.68)",
    textShadowRadius: 4
  }
});
