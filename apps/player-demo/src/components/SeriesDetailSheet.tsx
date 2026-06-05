import { Ionicons } from "@expo/vector-icons";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  FlatList,
  Image,
  Modal,
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View
} from "react-native";
import type { SeriesGroup } from "../domain/playerFeed";
import type { PlayerVideo } from "../domain/playerApi";
import { getSeriesCoverSource } from "../domain/seriesCovers";
import { colors, radii, spacing } from "../theme";

type DetailTab = "summary" | "episodes";

const DRAG_DISMISS_DISTANCE_PX = 72;
const DRAG_DISMISS_VELOCITY = 0.72;
const SHEET_ENTER_DURATION_MS = 220;
const SHEET_EXIT_DURATION_MS = 160;

export function SeriesDetailSheet({
  visible,
  series,
  currentVideoId,
  onClose,
  onSelectEpisode
}: {
  visible: boolean;
  series: SeriesGroup | undefined;
  currentVideoId: string | undefined;
  onClose: () => void;
  onSelectEpisode: (video: PlayerVideo) => void;
}) {
  const [activeTab, setActiveTab] = useState<DetailTab>("summary");
  const dragY = useRef(new Animated.Value(0)).current;
  const viewport = useWindowDimensions();
  const offscreenY = Math.max(1, viewport.height);
  const episodeRanges = useMemo(() => {
    if (!series) {
      return [];
    }
    const ranges: string[] = [];
    for (let start = 1; start <= series.episodeCount; start += 30) {
      ranges.push(`${start}-${Math.min(start + 29, series.episodeCount)}`);
    }
    return ranges;
  }, [series]);
  const closeWithSheetAnimation = useCallback(() => {
    Animated.timing(dragY, {
      toValue: offscreenY,
      duration: SHEET_EXIT_DURATION_MS,
      useNativeDriver: true
    }).start(({ finished }) => {
      if (finished) {
        onClose();
        requestAnimationFrame(() => {
          dragY.setValue(0);
        });
      }
    });
  }, [dragY, offscreenY, onClose]);

  useEffect(() => {
    if (!visible) {
      return;
    }
    dragY.setValue(offscreenY);
    Animated.timing(dragY, {
      toValue: 0,
      duration: SHEET_ENTER_DURATION_MS,
      useNativeDriver: true
    }).start();
  }, [dragY, offscreenY, visible]);

  const topEdgePanResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, gestureState) =>
          gestureState.dy > 4 && Math.abs(gestureState.dy) > Math.abs(gestureState.dx),
        onPanResponderMove: (_, gestureState) => {
          dragY.setValue(Math.max(0, gestureState.dy));
        },
        onPanResponderRelease: (_, gestureState) => {
          if (gestureState.dy >= DRAG_DISMISS_DISTANCE_PX || gestureState.vy >= DRAG_DISMISS_VELOCITY) {
            closeWithSheetAnimation();
            return;
          }
          Animated.spring(dragY, {
            toValue: 0,
            useNativeDriver: true
          }).start();
        },
        onPanResponderTerminate: () => {
          Animated.spring(dragY, {
            toValue: 0,
            useNativeDriver: true
          }).start();
        }
      }),
    [closeWithSheetAnimation, dragY]
  );

  if (!series) {
    return null;
  }
  const coverSource = getSeriesCoverSource(series.coverVideo.seriesId) ?? { uri: series.coverVideo.streamUrl };

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={closeWithSheetAnimation}>
      <Pressable style={styles.backdrop} onPress={closeWithSheetAnimation} />
      <Animated.View style={[styles.sheet, { transform: [{ translateY: dragY }] }]}>
        <View style={styles.topDragArea} {...topEdgePanResponder.panHandlers}>
          <View style={styles.handle} />
        </View>
        <View style={styles.header}>
          <Image source={coverSource} style={styles.poster} />
          <View style={styles.headerText}>
            <Text numberOfLines={1} style={styles.title}>
              {series.title} ›
            </Text>
            <Text style={styles.meta}>已完结 共{series.episodeCount}集</Text>
          </View>
        </View>
        <View style={styles.tabs}>
          <Pressable accessibilityRole="button" accessibilityLabel="查看简介" onPress={() => setActiveTab("summary")}>
            <Text style={[styles.tab, activeTab === "summary" ? styles.activeTab : null]}>简介</Text>
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel="查看选集" onPress={() => setActiveTab("episodes")}>
            <Text style={[styles.tab, activeTab === "episodes" ? styles.activeTab : null]}>选集</Text>
          </Pressable>
        </View>
        {activeTab === "summary" ? (
          <View accessible accessibilityLabel="剧情简介面板" style={styles.summaryPanel}>
            <Text style={styles.summary}>{series.summary}</Text>
          </View>
        ) : (
          <View accessible accessibilityLabel="选集列表" style={styles.episodesPanel}>
            <View style={styles.ranges}>
              {episodeRanges.map((range, index) => (
                <Text key={range} style={[styles.range, index === 0 ? styles.activeRange : null]}>
                  {range}
                </Text>
              ))}
            </View>
            <FlatList
              data={series.episodes}
              keyExtractor={(item) => item.videoId}
              numColumns={6}
              scrollEnabled
              contentContainerStyle={styles.episodeGrid}
              renderItem={({ item, index }) => {
                const isActive = item.videoId === currentVideoId;
                const label = item.episodeNo ?? index + 1;
                return (
                  <Pressable
                    accessibilityRole="button"
                    style={[styles.episodeCell, isActive ? styles.activeEpisodeCell : null]}
                    onPress={() => onSelectEpisode(item)}
                  >
                    {isActive ? <Ionicons name="stats-chart" size={13} color={colors.accent} style={styles.nowIcon} /> : null}
                    <Text style={[styles.episodeText, isActive ? styles.activeEpisodeText : null]}>{label}</Text>
                  </Pressable>
                );
              }}
            />
          </View>
        )}
      </Animated.View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "transparent"
  },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    minHeight: "54%",
    maxHeight: "72%",
    paddingTop: 10,
    paddingHorizontal: 22,
    paddingBottom: 26,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    backgroundColor: colors.text
  },
  handle: {
    alignSelf: "center",
    width: 50,
    height: 5,
    borderRadius: 3,
    backgroundColor: "#D8D8D8"
  },
  topDragArea: {
    height: 28,
    justifyContent: "flex-start"
  },
  header: {
    marginTop: 6,
    flexDirection: "row",
    alignItems: "center"
  },
  poster: {
    width: 62,
    height: 82,
    borderRadius: radii.small,
    backgroundColor: "#E8E8E8"
  },
  headerText: {
    flex: 1,
    marginLeft: 14
  },
  title: {
    color: "#111",
    fontSize: 20,
    fontWeight: "800"
  },
  meta: {
    marginTop: 7,
    color: "#909090",
    fontSize: 15,
    fontWeight: "600"
  },
  tabs: {
    marginTop: 30,
    flexDirection: "row",
    gap: 34
  },
  tab: {
    color: "#9A9A9A",
    fontSize: 21,
    fontWeight: "700"
  },
  activeTab: {
    color: "#111",
    fontWeight: "800"
  },
  summaryPanel: {
    marginTop: 18
  },
  summary: {
    color: "#111",
    fontSize: 18,
    fontWeight: "600",
    lineHeight: 29
  },
  episodesPanel: {
    flex: 1,
    marginTop: 22
  },
  ranges: {
    flexDirection: "row",
    gap: 40,
    marginBottom: 15
  },
  range: {
    color: "#999",
    fontSize: 16,
    fontWeight: "600"
  },
  activeRange: {
    color: "#111",
    fontWeight: "700"
  },
  episodeGrid: {
    paddingBottom: 24
  },
  episodeCell: {
    width: "15.2%",
    aspectRatio: 1,
    marginRight: "1.7%",
    marginBottom: spacing.md,
    borderRadius: radii.small,
    backgroundColor: "#F5F5F5",
    alignItems: "center",
    justifyContent: "center"
  },
  activeEpisodeCell: {
    backgroundColor: "#FFF1E5"
  },
  nowIcon: {
    position: "absolute",
    top: 9,
    right: 10
  },
  episodeText: {
    color: "#171717",
    fontSize: 18,
    fontWeight: "700"
  },
  activeEpisodeText: {
    color: colors.accent
  }
});
