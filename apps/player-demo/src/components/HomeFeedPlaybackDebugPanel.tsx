import { memo, useState, useSyncExternalStore } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  formatHomeFeedPlaybackEvent,
  formatHomeFeedPlaybackLatency,
  formatHomeFeedPlaybackPage
} from "../domain/homeFeedPlaybackDebug";
import type { HomeFeedPlaybackObserver } from "../domain/homeFeedPlaybackObserver";
import { colors, radii, spacing } from "../theme";

export const HomeFeedPlaybackDebugPanel = memo(function HomeFeedPlaybackDebugPanel({
  observer
}: {
  observer: HomeFeedPlaybackObserver;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const snapshot = useSyncExternalStore(observer.subscribe, observer.getSnapshot, observer.getSnapshot);
  const mountedPages = snapshot.pages.filter((page) => page.isMounted);
  const recentEvents = snapshot.events.slice(-6).reverse();

  return (
    <View pointerEvents="box-none" style={styles.root}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={isOpen ? "关闭 Home Feed 播放观测" : "打开 Home Feed 播放观测"}
        style={[styles.toggle, isOpen && styles.toggleOpen]}
        onPress={() => setIsOpen((current) => !current)}
      >
        <Text style={styles.toggleText}>DBG</Text>
      </Pressable>
      {isOpen ? (
        <View style={styles.panel}>
          <View style={styles.panelHeader}>
            <View>
              <Text style={styles.eyebrow}>HOME FEED / PLAYBACK</Text>
              <Text numberOfLines={1} style={styles.activeTitle}>
                {snapshot.activeVideoId ?? "waiting for active video"}
              </Text>
            </View>
            <Pressable accessibilityRole="button" hitSlop={8} onPress={observer.clear}>
              <Text style={styles.clearText}>CLEAR</Text>
            </Pressable>
          </View>

          <View style={styles.metricsRow}>
            <View style={styles.metric}>
              <Text style={styles.metricLabel}>ACTIVE</Text>
              <Text style={styles.metricValue}>{snapshot.activeIndex ?? "—"}</Text>
            </View>
            <View style={styles.metric}>
              <Text style={styles.metricLabel}>PLAYING</Text>
              <Text style={styles.metricValue}>
                {formatHomeFeedPlaybackLatency(snapshot.switchMetrics?.playingLatencyMs)}
              </Text>
            </View>
            <View style={styles.metric}>
              <Text style={styles.metricLabel}>FIRST FRAME</Text>
              <Text style={styles.metricValue}>
                {formatHomeFeedPlaybackLatency(snapshot.switchMetrics?.firstFrameLatencyMs)}
              </Text>
            </View>
          </View>

          <Text style={styles.sectionLabel}>MOUNTED PAGES</Text>
          <View style={styles.sectionBody}>
            {mountedPages.length > 0 ? (
              mountedPages.map((page) => (
                <Text
                  key={`${page.pageIndex}:${page.videoId}`}
                  numberOfLines={1}
                  style={[styles.monoLine, page.hasPlaybackOwnership && styles.ownerLine]}
                >
                  {formatHomeFeedPlaybackPage(page)}
                </Text>
              ))
            ) : (
              <Text style={styles.emptyText}>No mounted pages recorded</Text>
            )}
          </View>

          <Text style={styles.sectionLabel}>RECENT EVENTS</Text>
          <View style={styles.sectionBody}>
            {recentEvents.length > 0 ? (
              recentEvents.map((event) => (
                <Text key={event.sequence} numberOfLines={1} style={styles.monoLine}>
                  {formatHomeFeedPlaybackEvent(event)}
                </Text>
              ))
            ) : (
              <Text style={styles.emptyText}>Events continue collecting while closed</Text>
            )}
          </View>
        </View>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 50
  },
  toggle: {
    position: "absolute",
    top: 92,
    right: spacing.md,
    minWidth: 44,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.24)",
    borderRadius: radii.pill,
    backgroundColor: "rgba(0,0,0,0.66)"
  },
  toggleOpen: {
    borderColor: "rgba(255,106,26,0.72)",
    backgroundColor: "rgba(232,58,18,0.88)"
  },
  toggleText: {
    color: colors.text,
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 1.1
  },
  panel: {
    position: "absolute",
    top: 128,
    right: spacing.md,
    width: 344,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.14)",
    borderRadius: radii.panel,
    backgroundColor: "rgba(5,7,9,0.92)",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.32,
    shadowRadius: 18,
    elevation: 12
  },
  panelHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: spacing.md
  },
  eyebrow: {
    color: "#79DFFF",
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1.4
  },
  activeTitle: {
    maxWidth: 248,
    marginTop: spacing.xs,
    color: colors.text,
    fontSize: 15,
    fontWeight: "800"
  },
  clearText: {
    color: colors.muted,
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1
  },
  metricsRow: {
    marginTop: spacing.md,
    flexDirection: "row",
    gap: spacing.sm
  },
  metric: {
    flex: 1,
    minHeight: 50,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderRadius: radii.small,
    backgroundColor: "rgba(255,255,255,0.06)"
  },
  metricLabel: {
    color: colors.muted,
    fontSize: 8,
    fontWeight: "800",
    letterSpacing: 0.8
  },
  metricValue: {
    marginTop: spacing.xs,
    color: colors.text,
    fontSize: 13,
    fontWeight: "900"
  },
  sectionLabel: {
    marginTop: spacing.md,
    color: "rgba(255,255,255,0.46)",
    fontSize: 8,
    fontWeight: "900",
    letterSpacing: 1.2
  },
  sectionBody: {
    marginTop: spacing.xs,
    gap: 3
  },
  monoLine: {
    color: "rgba(255,255,255,0.72)",
    fontFamily: "monospace",
    fontSize: 9,
    lineHeight: 13
  },
  ownerLine: {
    color: "#FFB36B"
  },
  emptyText: {
    color: "rgba(255,255,255,0.38)",
    fontSize: 10,
    fontStyle: "italic"
  }
});
