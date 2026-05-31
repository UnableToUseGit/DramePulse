import { Ionicons } from "@expo/vector-icons";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { SeriesSummary } from "../domain/seriesCatalog";
import type { PlayerVideo } from "../domain/playerApi";
import { colors, radii, spacing } from "../theme";

export function TheaterScreen({
  seriesList,
  onClose,
  onPlaySeries
}: {
  seriesList: SeriesSummary[];
  onClose: () => void;
  onPlaySeries: (video: PlayerVideo) => void;
}) {
  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>剧场</Text>
          <Text style={styles.subtitle}>共 {seriesList.length} 部短剧</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="关闭剧场" style={styles.closeButton} onPress={onClose}>
          <Ionicons name="close" size={24} color={colors.text} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.list} showsVerticalScrollIndicator={false}>
        {seriesList.map((series, index) => {
          const firstEpisode = series.episodes[0];
          if (!firstEpisode) {
            return null;
          }
          return (
            <Pressable
              key={series.id}
              accessibilityRole="button"
              accessibilityLabel={`播放${series.title}第一集`}
              style={styles.card}
              onPress={() => onPlaySeries(firstEpisode)}
            >
              <View style={[styles.poster, index % 2 === 0 ? styles.posterWarm : styles.posterCool]}>
                <Text numberOfLines={2} style={styles.posterText}>
                  {series.title}
                </Text>
                <Text style={styles.posterBadge}>{series.episodes.length} 集</Text>
              </View>
              <View style={styles.cardBody}>
                <Text numberOfLines={1} style={styles.seriesTitle}>
                  {series.title}
                </Text>
                <Text numberOfLines={2} style={styles.summary}>
                  {series.plotSummary}
                </Text>
                <View style={styles.metaRow}>
                  <Text style={styles.metaTag}>短剧</Text>
                  <Text style={styles.metaTag}>{series.episodes.length} 集</Text>
                  <Text style={styles.metaTag}>{Math.max(1, Math.round(series.totalDuration / 60))} 分钟</Text>
                </View>
              </View>
              <Ionicons name="play-circle" size={34} color={colors.accent} />
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    paddingTop: 54,
    backgroundColor: "#101013",
    zIndex: 40
  },
  header: {
    paddingHorizontal: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  title: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "900"
  },
  subtitle: {
    marginTop: spacing.xs,
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700"
  },
  closeButton: {
    width: 42,
    height: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 21,
    backgroundColor: "rgba(255,255,255,0.1)"
  },
  list: {
    padding: spacing.lg,
    paddingBottom: 34,
    gap: spacing.md
  },
  card: {
    minHeight: 138,
    padding: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderRadius: radii.small,
    backgroundColor: "rgba(255,255,255,0.08)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)"
  },
  poster: {
    width: 86,
    height: 116,
    padding: spacing.sm,
    justifyContent: "space-between",
    borderRadius: radii.small
  },
  posterWarm: {
    backgroundColor: "#8F321B"
  },
  posterCool: {
    backgroundColor: "#243D68"
  },
  posterText: {
    color: colors.text,
    fontSize: 16,
    lineHeight: 21,
    fontWeight: "900"
  },
  posterBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.small,
    color: colors.text,
    backgroundColor: "rgba(0,0,0,0.32)",
    fontSize: 11,
    fontWeight: "800"
  },
  cardBody: {
    flex: 1,
    minWidth: 0
  },
  seriesTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900"
  },
  summary: {
    marginTop: spacing.xs,
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
    fontWeight: "700"
  },
  metaRow: {
    marginTop: spacing.sm,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs
  },
  metaTag: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radii.small,
    color: colors.text,
    backgroundColor: "rgba(255,255,255,0.12)",
    fontSize: 11,
    fontWeight: "800"
  }
});
