import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { API_BASE_URL, API_REQUEST_TIMEOUT_MS } from "./src/config";
import { getSeriesResumeTarget, groupVideosBySeries, SeriesGroup } from "./src/domain/playerFeed";
import { loadPlayerVideos, PlayerVideo } from "./src/domain/playerApi";
import { HomeFeedScreen } from "./src/screens/HomeFeedScreen";
import { SeriesPlayerScreen } from "./src/screens/SeriesPlayerScreen";
import { TheaterScreen } from "./src/screens/TheaterScreen";
import { colors, radii, spacing } from "./src/theme";

type AppRoute = "home" | "theater" | "series-player";

export default function App() {
  const [route, setRoute] = useState<AppRoute>("home");
  const [videos, setVideos] = useState<PlayerVideo[]>([]);
  const [selectedSeriesKey, setSelectedSeriesKey] = useState<string | undefined>();
  const [playbackPositions, setPlaybackPositions] = useState<Record<string, number>>({});
  const [seriesResumeVideoIds, setSeriesResumeVideoIds] = useState<Record<string, string>>({});
  const [theaterScrollOffset, setTheaterScrollOffset] = useState(0);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<string | undefined>();
  const seriesList = useMemo(() => groupVideosBySeries(videos), [videos]);
  const selectedSeries = seriesList.find((item) => item.seriesKey === selectedSeriesKey);

  const fetchVideos = useCallback(async () => {
    setLoadState("loading");
    setLoadError(undefined);
    try {
      const nextVideos = await loadPlayerVideos({ apiBaseUrl: API_BASE_URL, timeoutMs: API_REQUEST_TIMEOUT_MS });
      setVideos(nextVideos);
      setLoadState("ready");
    } catch (error: unknown) {
      setLoadError(error instanceof Error ? error.message : "无法连接后端服务");
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    fetchVideos();
  }, [fetchVideos]);

  const handleSelectSeries = useCallback(
    (series: SeriesGroup) => {
      const target = getSeriesResumeTarget({
        series,
        seriesResumeVideoIds,
        playbackPositions
      });
      setSelectedSeriesKey(series.seriesKey);
      setSeriesResumeVideoIds((records) => ({
        ...records,
        [series.seriesKey]: target.video.videoId
      }));
      setRoute("series-player");
    },
    [playbackPositions, seriesResumeVideoIds]
  );

  const handleSeriesResumeVideoChange = useCallback((seriesKey: string, videoId: string) => {
    setSeriesResumeVideoIds((records) => ({
      ...records,
      [seriesKey]: videoId
    }));
  }, []);

  if (loadState === "loading") {
    return (
      <View style={[styles.root, styles.centerState]}>
        <StatusBar style="light" hidden />
        <Text style={styles.stateTitle}>正在连接后端视频源</Text>
        <Text style={styles.stateText}>GET {API_BASE_URL}/api/videos</Text>
      </View>
    );
  }

  if (loadState === "error") {
    return (
      <View style={[styles.root, styles.centerState]}>
        <StatusBar style="light" hidden />
        <Text style={styles.stateTitle}>无法加载剧场数据</Text>
        <Text style={styles.stateText}>{loadError ?? "请确认 services/api 已启动"}</Text>
        <Pressable style={styles.retryButton} onPress={fetchVideos}>
          <Text style={styles.retryText}>重试</Text>
        </Pressable>
      </View>
    );
  }

  const selectedResumeVideoId = selectedSeries ? seriesResumeVideoIds[selectedSeries.seriesKey] : undefined;

  return (
    <>
      <StatusBar style="light" hidden />
      {route === "theater" ? (
        <TheaterScreen
          series={seriesList}
          resumeVideoIds={seriesResumeVideoIds}
          initialScrollOffset={theaterScrollOffset}
          onSelectSeries={handleSelectSeries}
          onScrollOffsetChange={setTheaterScrollOffset}
          onOpenHome={() => setRoute("home")}
        />
      ) : route === "series-player" && selectedSeries ? (
        <SeriesPlayerScreen
          series={selectedSeries}
          initialVideoId={selectedResumeVideoId}
          playbackPositions={playbackPositions}
          onPlaybackPositionsChange={setPlaybackPositions}
          onBack={() => setRoute("theater")}
          onResumeVideoChange={handleSeriesResumeVideoChange}
        />
      ) : (
        <HomeFeedScreen
          videos={videos}
          playbackPositions={playbackPositions}
          onPlaybackPositionsChange={setPlaybackPositions}
          onOpenTheater={() => setRoute("theater")}
        />
      )}
    </>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.black
  },
  centerState: {
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl
  },
  stateTitle: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "900",
    textAlign: "center"
  },
  stateText: {
    marginTop: spacing.sm,
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700",
    textAlign: "center"
  },
  retryButton: {
    marginTop: spacing.lg,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
    borderRadius: radii.small,
    backgroundColor: colors.accent
  },
  retryText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "900"
  }
});
