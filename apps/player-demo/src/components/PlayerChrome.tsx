import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";

export function PlayerChrome({
  onToggleDebug,
  seriesName,
  title,
  episodeLabel
}: {
  onToggleDebug: () => void;
  seriesName?: string;
  title: string;
  episodeLabel?: string;
}) {
  return (
    <View pointerEvents="box-none" style={styles.root}>
      <View style={styles.top}>
        <Ionicons name="menu" size={30} color="#fff" />
        <View style={styles.topActions}>
          <Ionicons name="search" size={27} color="#fff" />
          <Pressable style={styles.debugButton} onPress={onToggleDebug}>
            <MaterialCommunityIcons name="chart-timeline-variant" size={20} color={colors.accent} />
          </Pressable>
        </View>
      </View>

      <View style={styles.rail}>
        <RailIcon icon="star" count="199.4万" />
        <RailIcon icon="chatbubble-ellipses" count="6626" />
        <RailIcon icon="heart" count="30.8万" />
        <RailIcon icon="arrow-redo" count="5.3万" />
      </View>

      <View style={styles.meta}>
        <View style={styles.badge}>
          <Ionicons name="play" size={14} color="#fff" />
          <Text style={styles.badgeText}>i说 系列剧 · {seriesName ?? "DramePulse"}</Text>
        </View>
        <Text numberOfLines={2} style={styles.title}>
          {title}
        </Text>
        <View style={styles.tags}>
          <Text style={styles.tag}>{episodeLabel ?? "短剧"}</Text>
          <Text style={styles.tag}>都市爱情</Text>
          <Text style={styles.tag}>真实弹幕</Text>
        </View>
        <Text numberOfLines={1} style={styles.description}>
          后端视频流 · SQLite videos 表
        </Text>
      </View>

      <View style={styles.bottomTab}>
        {["首页", "剧场", "商城", "福利", "我的"].map((item, index) => (
          <Text key={item} style={[styles.tabText, index === 0 ? styles.activeTab : null]}>
            {item}
          </Text>
        ))}
      </View>
    </View>
  );
}

function RailIcon({ icon, count }: { icon: keyof typeof Ionicons.glyphMap; count: string }) {
  return (
    <View style={styles.railItem}>
      <Ionicons name={icon} size={42} color="#fff" />
      <Text style={styles.railText}>{count}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject
  },
  top: {
    position: "absolute",
    top: 48,
    left: spacing.lg,
    right: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  topActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md
  },
  debugButton: {
    width: 34,
    height: 34,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 17,
    backgroundColor: colors.panel
  },
  rail: {
    position: "absolute",
    right: spacing.md,
    bottom: 158,
    alignItems: "center",
    gap: spacing.lg
  },
  railItem: {
    alignItems: "center",
    gap: spacing.xs
  },
  railText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    textShadowColor: "rgba(0,0,0,0.68)",
    textShadowRadius: 4
  },
  meta: {
    position: "absolute",
    left: spacing.lg,
    right: 88,
    bottom: 92
  },
  badge: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.small,
    backgroundColor: "rgba(0,0,0,0.44)"
  },
  badgeText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700"
  },
  title: {
    marginTop: spacing.sm,
    color: colors.text,
    fontSize: 22,
    fontWeight: "900"
  },
  tags: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.sm
  },
  tag: {
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.small,
    color: colors.text,
    backgroundColor: "rgba(255,255,255,0.18)",
    fontSize: 13,
    fontWeight: "700"
  },
  description: {
    marginTop: spacing.sm,
    color: colors.text,
    fontSize: 17,
    fontWeight: "700"
  },
  bottomTab: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 74,
    paddingHorizontal: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "rgba(18,18,18,0.94)"
  },
  tabText: {
    color: "rgba(255,255,255,0.52)",
    fontSize: 20,
    fontWeight: "900"
  },
  activeTab: {
    color: colors.text
  }
});
