import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { API_BASE_URL, API_REQUEST_TIMEOUT_MS, ENABLE_FAST_STARTUP } from "./src/config";
import { loadSeriesEpisodes } from "./src/domain/playerDataApi";
import { createPlaybackAssetCache, type PlaybackAssetCache } from "./src/domain/playbackAssetCache";
import { getSeriesResumeTarget, groupVideosBySeries, SeriesGroup } from "./src/domain/playerFeed";
import type { PlayerVideo } from "./src/domain/playerApi";
import { loadStartupData, TheaterSeriesGroup } from "./src/domain/startupLoader";
import { HomeFeedScreen } from "./src/screens/HomeFeedScreen";
import { SeriesPlayerScreen } from "./src/screens/SeriesPlayerScreen";
import { TheaterScreen } from "./src/screens/TheaterScreen";
import { colors, radii, spacing } from "./src/theme";

type AppRoute = "home" | "theater" | "series-player";

export default function App() {
  const [route, setRoute] = useState<AppRoute>("home");
  const [homeVideos, setHomeVideos] = useState<PlayerVideo[]>([]);
  const [theaterSeries, setTheaterSeries] = useState<TheaterSeriesGroup[]>([]);
  const [selectedSeriesKey, setSelectedSeriesKey] = useState<string | undefined>();
  const [playbackPositions, setPlaybackPositions] = useState<Record<string, number>>({});
  const [seriesResumeVideoIds, setSeriesResumeVideoIds] = useState<Record<string, string>>({});
  const [theaterScrollOffset, setTheaterScrollOffset] = useState(0);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [hasInitialVideoPlaybackReady, setHasInitialVideoPlaybackReady] = useState(false);
  const [loadError, setLoadError] = useState<string | undefined>();
  const playbackAssetCacheRef = useRef<PlaybackAssetCache | undefined>(undefined);
  if (playbackAssetCacheRef.current === undefined) {
    playbackAssetCacheRef.current = createPlaybackAssetCache();
  }
  const playbackAssetCache = playbackAssetCacheRef.current;
  const selectedSeries = theaterSeries.find((item): item is TheaterSeriesGroup & SeriesGroup => (
    item.seriesKey === selectedSeriesKey &&
    Array.isArray(item.episodes) &&
    item.episodes.length > 0 &&
    item.coverVideo !== undefined
  ));

  const fetchVideos = useCallback(async () => {
    setLoadState("loading");
    setHasInitialVideoPlaybackReady(false);
    setLoadError(undefined);
    try {
      const startup = await loadStartupData({
        apiBaseUrl: API_BASE_URL,
        cache: playbackAssetCache,
        timeoutMs: API_REQUEST_TIMEOUT_MS,
        skipPreload: ENABLE_FAST_STARTUP
      });
      setHomeVideos(startup.homeVideos);
      setTheaterSeries(startup.theaterSeries);
      setLoadState("ready");
    } catch (error: unknown) {
      setLoadError(error instanceof Error ? error.message : "无法连接后端服务");
      setLoadState("error");
    }
  }, [playbackAssetCache]);

  useEffect(() => {
    fetchVideos();
  }, [fetchVideos]);

  const handleSelectSeries = useCallback(
    async (series: TheaterSeriesGroup) => {
      let playableSeries = series;
      if (!playableSeries.episodes || !playableSeries.coverVideo) {
        if (!series.seriesId) {
          return;
        }
        const episodes = await loadSeriesEpisodes({
          apiBaseUrl: API_BASE_URL,
          seriesId: series.seriesId,
          timeoutMs: API_REQUEST_TIMEOUT_MS
        });
        const grouped = groupVideosBySeries(episodes)[0];
        if (!grouped) {
          return;
        }
        playableSeries = {
          ...series,
          ...grouped,
          title: series.title,
          summary: series.summary,
          episodeCount: series.episodeCount || grouped.episodeCount,
          ...(series.coverUrl ? { coverUrl: series.coverUrl } : {})
        };
        setTheaterSeries((items) => items.map((item) => (item.seriesKey === series.seriesKey ? playableSeries : item)));
      }
      const target = getSeriesResumeTarget({
        series: playableSeries as SeriesGroup,
        seriesResumeVideoIds,
        playbackPositions
      });
      setSelectedSeriesKey(playableSeries.seriesKey);
      setSeriesResumeVideoIds((records) => ({
        ...records,
        [playableSeries.seriesKey]: target.video.videoId
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

  const shouldShowStartupOverlay =
    loadState === "loading" || (!ENABLE_FAST_STARTUP && loadState === "ready" && !hasInitialVideoPlaybackReady);

  const startupOverlay = shouldShowStartupOverlay ? (
    <View style={[styles.startupOverlay, styles.centerState]} pointerEvents="auto">
      <StatusBar style="dark" hidden />
      <View style={styles.bootLogo} accessibilityRole="image" accessibilityLabel="DramePulse Logo">
        <View style={[styles.bootLogoPulse, styles.bootLogoPulseShort]} />
        <View style={[styles.bootLogoPulse, styles.bootLogoPulseTall]} />
        <View style={[styles.bootLogoPulse, styles.bootLogoPulseMid]} />
        <View style={[styles.bootLogoPulse, styles.bootLogoPulseShort]} />
      </View>
      <Text style={styles.bootBrandText}>DramePulse</Text>
    </View>
  ) : null;

  if (loadState === "loading" && homeVideos.length === 0) {
    return (
      <View style={styles.root}>
        {startupOverlay}
      </View>
    );
  }

  if (loadState === "error") {
    return (
      <View style={[styles.root, styles.centerState]}>
        <StatusBar style="light" hidden />
        <Text style={styles.stateTitle}>无法加载剧场数据</Text>
        <Text style={styles.stateText}>{loadError ?? "请确认 services/api 已启动"}</Text>
        <Text style={styles.stateText}>API 地址：{API_BASE_URL}</Text>
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
          series={theaterSeries}
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
          playbackAssetCache={playbackAssetCache}
          playbackPositions={playbackPositions}
          onPlaybackPositionsChange={setPlaybackPositions}
          onBack={() => {
            setSelectedSeriesKey(undefined);
            setRoute("theater");
          }}
          onResumeVideoChange={handleSeriesResumeVideoChange}
        />
      ) : (
        <HomeFeedScreen
          videos={homeVideos}
          playbackAssetCache={playbackAssetCache}
          playbackPositions={playbackPositions}
          onPlaybackPositionsChange={setPlaybackPositions}
          onInitialVideoPlaybackReady={() => setHasInitialVideoPlaybackReady(true)}
          onOpenTheater={() => setRoute("theater")}
        />
      )}
      {startupOverlay}
    </>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.black
  },
  startupOverlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 50,
    backgroundColor: "#FFFFFF"
  },
  centerState: {
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl
  },
  bootLogo: {
    width: 86,
    height: 86,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 6,
    borderRadius: 26,
    borderWidth: 1,
    borderColor: "rgba(255, 106, 26, 0.22)",
    backgroundColor: "rgba(255, 106, 26, 0.08)",
    boxShadow: "0 18px 42px rgba(255, 74, 18, 0.18)"
  },
  bootLogoPulse: {
    width: 8,
    borderRadius: radii.pill,
    backgroundColor: colors.accent
  },
  bootLogoPulseShort: {
    height: 24,
    opacity: 0.66
  },
  bootLogoPulseMid: {
    height: 38,
    opacity: 0.86
  },
  bootLogoPulseTall: {
    height: 52,
    backgroundColor: colors.gold
  },
  bootBrandText: {
    marginTop: spacing.lg,
    color: colors.black,
    fontSize: 29,
    fontWeight: "700",
    letterSpacing: 0.4
  },
  stateTitle: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "900",
    textAlign: "center"
  },
  stateText: {
    marginTop: spacing.sm,
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700",
    textAlign: "center",
    lineHeight: 19
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
