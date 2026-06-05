import { Ionicons } from "@expo/vector-icons";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
import { colors, radii, spacing } from "../theme";
import { DanmakuEntryArea } from "./DanmakuEntryArea";

export function PlayerMeta({
  title,
  plotSummary,
  episodeLabel,
  metaTags,
  currentTime,
  isActive,
  showInnerVoice,
  showDanmakuEntry = true,
  showTags = true,
  summaryPresentation = "card",
  reserveActionRail = true,
  bottomOffset = 118,
  preTitleAccessory,
  onInnerVoiceGestureActiveChange,
  onSendInnerVoiceDanmaku
}: {
  title: string;
  plotSummary: string;
  episodeLabel?: string;
  metaTags?: string[];
  currentTime: number;
  isActive: boolean;
  showInnerVoice: boolean;
  showDanmakuEntry?: boolean;
  showTags?: boolean;
  summaryPresentation?: "card" | "inline";
  reserveActionRail?: boolean;
  bottomOffset?: number;
  preTitleAccessory?: ReactNode;
  onInnerVoiceGestureActiveChange: (active: boolean) => void;
  onSendInnerVoiceDanmaku: (cue: InnerVoiceDanmakuCue) => void;
}) {
  const titleCanExpand = Array.from(title).length > 9;
  const [isTitleExpanded, setIsTitleExpanded] = useState(false);
  const [isSummaryExpanded, setIsSummaryExpanded] = useState(false);
  const resolvedTags = metaTags ?? ["9.3分", "热榜第一", "演员·张伟"];

  useEffect(() => {
    setIsTitleExpanded(false);
    setIsSummaryExpanded(false);
  }, [title, plotSummary]);

  return (
    <View style={[styles.root, reserveActionRail ? styles.withActionRail : styles.fullWidth, { bottom: bottomOffset }]}>
      {showDanmakuEntry ? (
        <DanmakuEntryArea
          currentTime={currentTime}
          isActive={isActive}
          showInnerVoice={showInnerVoice}
          onInnerVoiceGestureActiveChange={onInnerVoiceGestureActiveChange}
          onSendInnerVoiceDanmaku={onSendInnerVoiceDanmaku}
        />
      ) : null}
      {preTitleAccessory ? <View style={styles.preTitleAccessory}>{preTitleAccessory}</View> : null}
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
      {showTags ? (
        <View style={styles.tags}>
          {resolvedTags.map((tag) => (
            <Text key={tag} numberOfLines={1} ellipsizeMode="tail" style={styles.tag}>
              {tag}
            </Text>
          ))}
        </View>
      ) : null}
      {summaryPresentation === "inline" ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isSummaryExpanded ? "收起剧情简介" : "展开剧情简介"}
          style={styles.inlineSummary}
          onPress={() => setIsSummaryExpanded((expanded) => !expanded)}
        >
          {isSummaryExpanded ? (
            <Text style={styles.inlineSummaryText}>
              {plotSummary} <Text style={styles.inlineSummaryAction}>收起</Text>
            </Text>
          ) : (
            <View style={styles.inlineSummaryCollapsed}>
              <Text numberOfLines={1} ellipsizeMode="tail" style={styles.inlineSummaryText}>
                {plotSummary}
              </Text>
              <Text style={styles.inlineSummaryAction}> 展开</Text>
            </View>
          )}
        </Pressable>
      ) : (
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
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.lg
  },
  withActionRail: {
    right: 100
  },
  fullWidth: {
    right: spacing.lg
  },
  title: {
    flex: 1,
    paddingRight: 18,
    color: colors.text,
    fontSize: 22,
    fontWeight: "900",
    letterSpacing: -0.2
  },
  titleRow: {
    alignSelf: "stretch",
    minHeight: 30,
    flexDirection: "row",
    alignItems: "flex-start"
  },
  preTitleAccessory: {
    alignSelf: "flex-start",
    marginBottom: spacing.sm
  },
  titleArrow: {
    position: "absolute",
    right: 0,
    top: 5
  },
  summaryCard: {
    alignSelf: "stretch",
    marginTop: spacing.sm,
    minHeight: 40,
    paddingHorizontal: spacing.md,
    paddingVertical: 7,
    borderRadius: 12,
    backgroundColor: "rgba(0,0,0,0.28)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)"
  },
  summaryText: {
    paddingRight: 18,
    color: "rgba(255,255,255,0.86)",
    fontSize: 13,
    fontWeight: "800",
    lineHeight: 18
  },
  summaryArrow: {
    position: "absolute",
    right: 7,
    bottom: 4
  },
  inlineSummary: {
    alignSelf: "stretch",
    marginTop: 12
  },
  inlineSummaryCollapsed: {
    flexDirection: "row",
    alignItems: "center"
  },
  inlineSummaryText: {
    flexShrink: 1,
    color: "rgba(255,255,255,0.84)",
    fontSize: 14,
    fontWeight: "800",
    lineHeight: 20
  },
  inlineSummaryAction: {
    color: "rgba(255,255,255,0.72)",
    fontSize: 14,
    fontWeight: "900"
  },
  tags: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.sm,
    maxHeight: 30,
    overflow: "hidden"
  },
  tag: {
    overflow: "hidden",
    maxWidth: 92,
    paddingHorizontal: 11,
    paddingVertical: 5,
    borderRadius: radii.small,
    color: colors.text,
    backgroundColor: "rgba(255,255,255,0.2)",
    fontSize: 13,
    fontWeight: "800"
  }
});
