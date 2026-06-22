import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, playerOverlay } from "../theme";

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
        <Ionicons name="heart" size={35} color={liked ? "#FF335F" : "#fff"} />
      </View>
      <Text style={styles.railText}>{count}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    alignItems: "center",
    width: 56,
    gap: 1
  },
  iconWrap: {
    width: 48,
    height: 40,
    alignItems: "center",
    justifyContent: "center"
  },
  railText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "400",
    fontVariant: ["tabular-nums"],
  }
});
