import { Ionicons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";

export function PlayerMeta({
  title,
  plotSummary,
  episodeLabel
}: {
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
    <View style={styles.root}>
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
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.lg,
    right: 100,
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
    marginTop: 6,
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
  }
});
