import { Ionicons } from "@expo/vector-icons";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { SeriesSummary } from "../domain/seriesCatalog";
import type { PlayerVideo } from "../domain/playerApi";
import { colors, radii, spacing } from "../theme";

function formatDuration(seconds: number) {
  const totalMinutes = Math.max(1, Math.round(seconds / 60));
  return `${totalMinutes} 分钟`;
}

function getEpisodeTitle(episode: PlayerVideo, index: number) {
  return episode.episodeLabel || `第 ${episode.episodeNo ?? index + 1} 集`;
}

export function SeriesDetailScreen({
  series,
  currentVideoId,
  onBack,
  onPlayEpisode
}: {
  series: SeriesSummary;
  currentVideoId?: string;
  onBack: () => void;
  onPlayEpisode: (video: PlayerVideo) => void;
}) {
  const firstEpisode = series.episodes[0];

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Pressable accessibilityRole="button" accessibilityLabel="返回播放页" style={styles.iconButton} onPress={onBack}>
          <Ionicons name="chevron-back" size={25} color={colors.text} />
        </Pressable>
        <Text numberOfLines={1} style={styles.headerTitle}>
          短剧详情
        </Text>
        <View style={styles.iconButtonPlaceholder} />
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <View style={styles.poster}>
            <Text numberOfLines={3} style={styles.posterTitle}>
              {series.title}
            </Text>
            <Text style={styles.posterBadge}>{series.episodes.length} 集</Text>
          </View>
          <View style={styles.heroInfo}>
            <Text numberOfLines={2} style={styles.title}>
              {series.title}
            </Text>
            <View style={styles.tags}>
              <Text style={styles.tag}>短剧</Text>
              <Text style={styles.tag}>{series.episodes.length} 集</Text>
              <Text style={styles.tag}>{formatDuration(series.totalDuration)}</Text>
            </View>
            <Text numberOfLines={4} style={styles.summary}>
              {series.plotSummary}
            </Text>
            {firstEpisode ? (
              <Pressable style={styles.primaryButton} onPress={() => onPlayEpisode(firstEpisode)}>
                <Ionicons name="play" size={18} color={colors.text} />
                <Text style={styles.primaryButtonText}>从第一集播放</Text>
              </Pressable>
            ) : null}
          </View>
        </View>

        <View style={styles.infoPanel}>
          <Text style={styles.sectionTitle}>已存短剧信息</Text>
          <View style={styles.infoGrid}>
            <InfoItem label="短剧 ID" value={series.id.replace(/^(id|name|video):/, "")} />
            <InfoItem label="可播放剧集" value={`${series.episodes.length} 集`} />
            <InfoItem label="视频源" value={`${series.episodes.length} 条`} />
            <InfoItem label="弹幕源" value={`${series.episodes.filter((episode) => episode.danmakuUrl).length} 条`} />
          </View>
        </View>

        <View style={styles.episodeSection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>选集观看</Text>
            <Text style={styles.sectionHint}>点击任一集从该集开始播放</Text>
          </View>
          <View style={styles.episodeGrid}>
            {series.episodes.map((episode, index) => {
              const isCurrent = episode.videoId === currentVideoId;
              return (
                <Pressable
                  key={episode.videoId}
                  accessibilityRole="button"
                  accessibilityLabel={`播放${getEpisodeTitle(episode, index)}`}
                  style={[styles.episodeButton, isCurrent ? styles.episodeButtonActive : null]}
                  onPress={() => onPlayEpisode(episode)}
                >
                  <Text numberOfLines={1} style={[styles.episodeText, isCurrent ? styles.episodeTextActive : null]}>
                    {getEpisodeTitle(episode, index)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoItem}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text numberOfLines={1} style={styles.infoValue}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    paddingTop: 48,
    backgroundColor: "#101013",
    zIndex: 45
  },
  header: {
    height: 48,
    paddingHorizontal: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  iconButton: {
    width: 42,
    height: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 21,
    backgroundColor: "rgba(255,255,255,0.1)"
  },
  iconButtonPlaceholder: {
    width: 42,
    height: 42
  },
  headerTitle: {
    flex: 1,
    paddingHorizontal: spacing.md,
    color: colors.text,
    fontSize: 18,
    fontWeight: "900",
    textAlign: "center"
  },
  content: {
    padding: spacing.lg,
    paddingBottom: 34
  },
  hero: {
    flexDirection: "row",
    gap: spacing.md
  },
  poster: {
    width: 116,
    height: 158,
    padding: spacing.md,
    justifyContent: "space-between",
    borderRadius: radii.small,
    backgroundColor: "#8F321B"
  },
  posterTitle: {
    color: colors.text,
    fontSize: 18,
    lineHeight: 24,
    fontWeight: "900"
  },
  posterBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: radii.small,
    color: colors.text,
    backgroundColor: "rgba(0,0,0,0.32)",
    fontSize: 12,
    fontWeight: "900"
  },
  heroInfo: {
    flex: 1,
    minWidth: 0
  },
  title: {
    color: colors.text,
    fontSize: 23,
    lineHeight: 29,
    fontWeight: "900"
  },
  tags: {
    marginTop: spacing.sm,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs
  },
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radii.small,
    color: colors.text,
    backgroundColor: "rgba(255,255,255,0.12)",
    fontSize: 11,
    fontWeight: "800"
  },
  summary: {
    marginTop: spacing.sm,
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
    fontWeight: "700"
  },
  primaryButton: {
    alignSelf: "flex-start",
    marginTop: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 9,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.accent
  },
  primaryButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900"
  },
  infoPanel: {
    marginTop: spacing.xl,
    padding: spacing.md,
    borderRadius: radii.small,
    backgroundColor: "rgba(255,255,255,0.08)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)"
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "900"
  },
  infoGrid: {
    marginTop: spacing.md,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  infoItem: {
    width: "48%",
    minHeight: 54,
    padding: spacing.sm,
    borderRadius: radii.small,
    backgroundColor: "rgba(0,0,0,0.24)"
  },
  infoLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "800"
  },
  infoValue: {
    marginTop: spacing.xs,
    color: colors.text,
    fontSize: 14,
    fontWeight: "900"
  },
  episodeSection: {
    marginTop: spacing.xl
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.md
  },
  sectionHint: {
    flexShrink: 1,
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    textAlign: "right"
  },
  episodeGrid: {
    marginTop: spacing.md,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  episodeButton: {
    width: "22.8%",
    height: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.small,
    backgroundColor: "rgba(255,255,255,0.1)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)"
  },
  episodeButtonActive: {
    backgroundColor: "rgba(255,106,26,0.18)",
    borderColor: "rgba(255,106,26,0.72)"
  },
  episodeText: {
    paddingHorizontal: 4,
    color: colors.text,
    fontSize: 13,
    fontWeight: "900"
  },
  episodeTextActive: {
    color: colors.gold
  }
});
