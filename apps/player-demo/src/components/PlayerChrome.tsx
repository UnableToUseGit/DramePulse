import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";
import { LikeReactionButton } from "./LikeReactionButton";
import { PlaybackRate, SpeedSelector } from "./SpeedSelector";

export function PlayerChrome({
  onToggleDebug,
  playbackRate,
  isSpeedMenuOpen,
  onToggleSpeedMenu,
  onSelectPlaybackRate,
  title,
  plotSummary,
  episodeLabel
}: {
  onToggleDebug: () => void;
  playbackRate: PlaybackRate;
  isSpeedMenuOpen: boolean;
  onToggleSpeedMenu: () => void;
  onSelectPlaybackRate: (rate: PlaybackRate) => void;
  title: string;
  plotSummary: string;
  episodeLabel?: string;
}) {
  const titleCanExpand = Array.from(title).length > 9;
  const [isTitleExpanded, setIsTitleExpanded] = useState(false);
  const [isSummaryExpanded, setIsSummaryExpanded] = useState(false);

  useEffect(() => {
    setIsTitleExpanded(false);
    setIsSummaryExpanded(false);
  }, [title, plotSummary]);

  return (
    <View pointerEvents="box-none" style={styles.root}>
      <View style={styles.top}>
        <Ionicons name="menu" size={30} color="#fff" />
        <View style={styles.topActions}>
          <Ionicons name="search" size={27} color="#fff" />
          <SpeedSelector
            selectedRate={playbackRate}
            isOpen={isSpeedMenuOpen}
            onToggle={onToggleSpeedMenu}
            onSelect={onSelectPlaybackRate}
          />
          <Pressable style={styles.debugButton} onPress={onToggleDebug}>
            <MaterialCommunityIcons name="chart-timeline-variant" size={20} color={colors.accent} />
          </Pressable>
        </View>
      </View>

      <View style={styles.rail}>
        <RailIcon icon="star" count="199.4万" />
        <RailIcon icon="chatbubble-ellipses" count="6626" />
        <LikeReactionButton count="30.8万" />
        <RailIcon icon="arrow-redo" count="5.3万" />
      </View>

      <View style={styles.meta}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isTitleExpanded ? "收起完整标题" : "展开完整标题"}
          disabled={!titleCanExpand}
          style={styles.titleRow}
          onPress={() => setIsTitleExpanded((expanded) => !expanded)}
        >
          <Text numberOfLines={isTitleExpanded ? undefined : 1} style={styles.title}>
            {title}
          </Text>
          {titleCanExpand ? (
            <Ionicons
              name={isTitleExpanded ? "chevron-up" : "chevron-forward"}
              size={16}
              color="rgba(255,255,255,0.56)"
              style={styles.titleArrow}
            />
          ) : null}
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isSummaryExpanded ? "收起剧情简介" : "展开剧情简介"}
          style={styles.summaryCard}
          onPress={() => setIsSummaryExpanded((expanded) => !expanded)}
        >
          <Text numberOfLines={isSummaryExpanded ? undefined : 2} style={styles.summaryText}>
            {plotSummary}
          </Text>
          <View style={styles.summaryArrow}>
            <Ionicons
              name={isSummaryExpanded ? "chevron-up" : "chevron-down"}
              size={16}
              color="rgba(255,255,255,0.56)"
            />
          </View>
        </Pressable>
        <View style={styles.tags}>
          <Text numberOfLines={1} ellipsizeMode="tail" style={styles.tag}>
            {episodeLabel ?? "短剧"}
          </Text>
          <Text numberOfLines={1} ellipsizeMode="tail" style={styles.tag}>
            都市爱情
          </Text>
          <Text numberOfLines={1} ellipsizeMode="tail" style={styles.tag}>
            真实弹幕
          </Text>
        </View>
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
      <View style={styles.railIconWrap}>
        <Ionicons name={icon} size={42} color="#fff" />
      </View>
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
    gap: spacing.sm
  },
  railItem: {
    alignItems: "center",
    width: 76,
    gap: spacing.xs
  },
  railIconWrap: {
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
  },
  meta: {
    position: "absolute",
    left: spacing.lg,
    right: 88,
    bottom: 118
  },
  title: {
    flex: 1,
    paddingRight: 18,
    color: colors.text,
    fontSize: 20,
    fontWeight: "900"
  },
  titleRow: {
    alignSelf: "stretch",
    minHeight: 28,
    flexDirection: "row",
    alignItems: "flex-start"
  },
  titleArrow: {
    position: "absolute",
    right: 0,
    top: 5
  },
  summaryCard: {
    alignSelf: "stretch",
    marginTop: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.small,
    backgroundColor: "rgba(0,0,0,0.38)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)"
  },
  summaryText: {
    paddingRight: 18,
    color: "rgba(255,255,255,0.82)",
    fontSize: 12,
    fontWeight: "700",
    lineHeight: 17
  },
  summaryArrow: {
    position: "absolute",
    right: 7,
    bottom: 4
  },
  tags: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: spacing.xs,
    maxHeight: 28,
    overflow: "hidden"
  },
  tag: {
    overflow: "hidden",
    maxWidth: 76,
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: radii.small,
    color: colors.text,
    backgroundColor: "rgba(255,255,255,0.18)",
    fontSize: 12,
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
