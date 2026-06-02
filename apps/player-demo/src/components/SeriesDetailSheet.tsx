import { Ionicons } from "@expo/vector-icons";
import { useMemo, useState } from "react";
import { FlatList, Image, Modal, Pressable, StyleSheet, Text, View } from "react-native";
import type { SeriesGroup } from "../domain/playerFeed";
import type { PlayerVideo } from "../domain/playerApi";
import { getSeriesCoverSource } from "../domain/seriesCovers";
import { colors, radii, spacing } from "../theme";

type DetailTab = "summary" | "episodes";

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

  if (!series) {
    return null;
  }
  const coverSource = getSeriesCoverSource(series.coverVideo.seriesId) ?? { uri: series.coverVideo.streamUrl };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose} />
      <View style={styles.sheet}>
        <View style={styles.handle} />
        <View style={styles.header}>
          <Image source={coverSource} style={styles.poster} />
          <View style={styles.headerText}>
            <Text numberOfLines={1} style={styles.title}>
              {series.title} ›
            </Text>
            <Text style={styles.meta}>已完结 共{series.episodeCount}集</Text>
          </View>
          <Pressable accessibilityRole="button" hitSlop={12} onPress={onClose}>
            <Ionicons name="close" size={24} color="#7D7D7D" />
          </Pressable>
        </View>
        <View style={styles.tabs}>
          <Pressable onPress={() => setActiveTab("summary")}>
            <Text style={[styles.tab, activeTab === "summary" ? styles.activeTab : null]}>简介</Text>
          </Pressable>
          <Pressable onPress={() => setActiveTab("episodes")}>
            <Text style={[styles.tab, activeTab === "episodes" ? styles.activeTab : null]}>选集</Text>
          </Pressable>
        </View>
        {activeTab === "summary" ? (
          <View style={styles.summaryPanel}>
            <Text style={styles.summary}>{series.summary}</Text>
            <View style={styles.tags}>
              {["短剧", "情绪高光", "真实弹幕"].map((tag) => (
                <Text key={tag} style={styles.tag}>
                  {tag} ›
                </Text>
              ))}
            </View>
          </View>
        ) : (
          <View style={styles.episodesPanel}>
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
        <Pressable style={styles.favoriteButton}>
          <Ionicons name="star-outline" size={24} color={colors.text} />
          <Text style={styles.favoriteText}>收藏</Text>
        </Pressable>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.18)"
  },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    minHeight: "58%",
    maxHeight: "74%",
    paddingTop: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: 32,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    backgroundColor: colors.text
  },
  handle: {
    alignSelf: "center",
    width: 54,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#E3E3E3"
  },
  header: {
    marginTop: spacing.xl,
    flexDirection: "row",
    alignItems: "center"
  },
  poster: {
    width: 66,
    height: 86,
    borderRadius: radii.small,
    backgroundColor: "#E8E8E8"
  },
  headerText: {
    flex: 1,
    marginLeft: spacing.md
  },
  title: {
    color: "#111",
    fontSize: 24,
    fontWeight: "900"
  },
  meta: {
    marginTop: spacing.sm,
    color: "#8A8A8A",
    fontSize: 17,
    fontWeight: "700"
  },
  tabs: {
    marginTop: 34,
    flexDirection: "row",
    gap: 36
  },
  tab: {
    color: "#9A9A9A",
    fontSize: 26,
    fontWeight: "900"
  },
  activeTab: {
    color: "#111"
  },
  summaryPanel: {
    marginTop: spacing.lg
  },
  summary: {
    color: "#111",
    fontSize: 22,
    fontWeight: "700",
    lineHeight: 34
  },
  tags: {
    marginTop: spacing.lg,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  tag: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.small,
    backgroundColor: "#F3F3F3",
    color: "#6D6D6D",
    fontSize: 17,
    fontWeight: "800"
  },
  episodesPanel: {
    flex: 1,
    marginTop: spacing.xl
  },
  ranges: {
    flexDirection: "row",
    gap: 46,
    marginBottom: spacing.lg
  },
  range: {
    color: "#999",
    fontSize: 19,
    fontWeight: "800"
  },
  activeRange: {
    color: "#111"
  },
  episodeGrid: {
    paddingBottom: 90
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
    fontSize: 22,
    fontWeight: "800"
  },
  activeEpisodeText: {
    color: colors.accent
  },
  favoriteButton: {
    position: "absolute",
    left: "29%",
    right: "29%",
    bottom: 22,
    height: 58,
    borderRadius: radii.small,
    backgroundColor: colors.accent,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm
  },
  favoriteText: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "900"
  }
});
