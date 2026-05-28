import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";
import { LikeReactionButton } from "./LikeReactionButton";

export function PlayerActionRail({
  liked,
  onToggleLike
}: {
  liked: boolean;
  onToggleLike: () => void;
}) {
  return (
    <View style={styles.root}>
      <RailIcon icon="star" count="199.4万" />
      <RailIcon icon="chatbubble-ellipses" count="6626" />
      <LikeReactionButton count="30.8万" liked={liked} onToggle={onToggleLike} />
      <RailIcon icon="arrow-redo" count="5.3万" />
    </View>
  );
}

function RailIcon({ icon, count }: { icon: keyof typeof Ionicons.glyphMap; count: string }) {
  return (
    <View style={styles.item}>
      <View style={styles.iconWrap}>
        <Ionicons name={icon} size={42} color="#fff" />
      </View>
      <Text style={styles.text}>{count}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    right: spacing.md,
    bottom: 158,
    alignItems: "center",
    gap: spacing.sm
  },
  item: {
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
  text: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    textShadowColor: "rgba(0,0,0,0.68)",
    textShadowRadius: 4
  }
});
