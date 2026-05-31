import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  FlatList,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View
} from "react-native";
import { PlayerPage } from "../components/PlayerPage";
import { SeriesDetailScreen } from "../components/SeriesDetailScreen";
import { StoryQaScreen } from "../components/StoryQaScreen";
import { TheaterScreen } from "../components/TheaterScreen";
import { API_BASE_URL, API_REQUEST_TIMEOUT_MS } from "../config";
import { findNextEpisodeIndex, getFeedPageIndex, shouldPreloadFeedPage } from "../domain/playerFeed";
import { loadPlayerVideos, PlayerVideo } from "../domain/playerApi";
import { buildSeriesCatalog, findSeriesForVideo } from "../domain/seriesCatalog";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { colors, radii, spacing } from "../theme";

type PlayerOverlay = "none" | "theater" | "seriesDetail" | "storyQa";

export function PlayerScreen() {
  const [videos, setVideos] = useState<PlayerVideo[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [playbackPositions, setPlaybackPositions] = useState<Record<string, number>>({});
  const [pageHeight, setPageHeight] = useState(0);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<string | undefined>();
  const [selectedPresentationType, setSelectedPresentationType] = useState<InteractionPresentationType>("poll_bar");
  const [overlay, setOverlay] = useState<PlayerOverlay>("none");
  const [selectedSeriesId, setSelectedSeriesId] = useState<string | undefined>();
  const [storyQaContext, setStoryQaContext] = useState<{ video: PlayerVideo; currentTime: number } | undefined>();
  const listRef = useRef<FlatList<PlayerVideo>>(null);
  const viewport = useWindowDimensions();
  const resolvedPageHeight = pageHeight > 0 ? pageHeight : viewport.height;
  const seriesList = useMemo(() => buildSeriesCatalog(videos), [videos]);
  const selectedSeries = useMemo(
    () => seriesList.find((series) => series.id === selectedSeriesId),
    [selectedSeriesId, seriesList]
  );

  const fetchVideos = useCallback(async () => {
    setLoadState("loading");
    setLoadError(undefined);
    try {
      const nextVideos = await loadPlayerVideos({ apiBaseUrl: API_BASE_URL, timeoutMs: API_REQUEST_TIMEOUT_MS });
      setVideos(nextVideos);
      setActiveIndex(0);
      setPlaybackPositions({});
      setOverlay("none");
      setSelectedSeriesId(undefined);
      setStoryQaContext(undefined);
      setLoadState("ready");
    } catch (error: unknown) {
      setLoadError(error instanceof Error ? error.message : "无法连接后端服务");
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoadState("loading");
    setLoadError(undefined);
    loadPlayerVideos({ apiBaseUrl: API_BASE_URL, timeoutMs: API_REQUEST_TIMEOUT_MS })
      .then((nextVideos) => {
        if (!cancelled) {
          setVideos(nextVideos);
          setActiveIndex(0);
          setPlaybackPositions({});
          setOverlay("none");
          setSelectedSeriesId(undefined);
          setStoryQaContext(undefined);
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "无法连接后端服务");
          setLoadState("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleMomentumScrollEnd = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const nextIndex = getFeedPageIndex({
        offsetY: event.nativeEvent.contentOffset.y,
        pageHeight: resolvedPageHeight,
        itemCount: videos.length
      });
      setActiveIndex(nextIndex);
    },
    [resolvedPageHeight, videos.length]
  );

  const handleChangePresentationType = useCallback((type: InteractionPresentationType) => {
    setSelectedPresentationType(type);
  }, []);

  const handlePlayNextEpisode = useCallback(
    (currentIndex: number) => {
      const nextIndex = findNextEpisodeIndex(videos, currentIndex);
      if (nextIndex === undefined) {
        return;
      }
      setActiveIndex(nextIndex);
      listRef.current?.scrollToIndex({ index: nextIndex, animated: true });
    },
    [videos]
  );

  const handlePlayVideo = useCallback(
    (video: PlayerVideo) => {
      const nextIndex = videos.findIndex((item) => item.videoId === video.videoId);
      if (nextIndex < 0) {
        return;
      }
      setOverlay("none");
      setSelectedSeriesId(undefined);
      setStoryQaContext(undefined);
      setActiveIndex(nextIndex);
      setPlaybackPositions((positions) => ({
        ...positions,
        [video.videoId]: 0
      }));
      listRef.current?.scrollToIndex({ index: nextIndex, animated: false });
    },
    [videos]
  );

  const handleOpenSeriesDetails = useCallback(
    (video: PlayerVideo) => {
      const series = findSeriesForVideo(videos, video);
      if (!series) {
        return;
      }
      setSelectedSeriesId(series.id);
      setOverlay("seriesDetail");
    },
    [videos]
  );

  const handleOpenStoryQaPage = useCallback((video: PlayerVideo, currentTime: number) => {
    setStoryQaContext({ video, currentTime });
    setOverlay("storyQa");
  }, []);

  const handlePlaybackPositionChange = useCallback((videoId: string, time: number) => {
    setPlaybackPositions((positions) => {
      if (positions[videoId] === time) {
        return positions;
      }
      return {
        ...positions,
        [videoId]: time
      };
    });
  }, []);

  if (loadState === "loading") {
    return (
      <View style={[styles.root, styles.centerState]}>
        <Text style={styles.stateTitle}>正在连接后端视频源</Text>
        <Text style={styles.stateText}>GET {API_BASE_URL}/api/videos</Text>
        <Text style={styles.stateText}>最多等待 {Math.round(API_REQUEST_TIMEOUT_MS / 1000)} 秒</Text>
      </View>
    );
  }

  if (loadState === "error") {
    return (
      <View style={[styles.root, styles.centerState]}>
        <Text style={styles.stateTitle}>无法加载播放器数据</Text>
        <Text style={styles.stateText}>{loadError ?? "请确认 services/api 已启动"}</Text>
        <Pressable style={styles.retryButton} onPress={fetchVideos}>
          <Text style={styles.retryText}>重试</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View
      style={styles.root}
      onLayout={(event) => {
        const nextHeight = event.nativeEvent.layout.height;
        if (nextHeight > 0) {
          setPageHeight(nextHeight);
        }
      }}
    >
      {resolvedPageHeight > 0 ? (
        <FlatList
          ref={listRef}
          data={videos}
          keyExtractor={(item) => item.videoId}
          renderItem={({ item, index }) => {
            const nextEpisodeIndex = findNextEpisodeIndex(videos, index);
            const nextEpisode = nextEpisodeIndex !== undefined ? videos[nextEpisodeIndex] : undefined;
            return (
              <PlayerPage
                video={item}
                isActive={index === activeIndex}
                shouldMountVideo={shouldPreloadFeedPage({ pageIndex: index, activeIndex })}
                height={resolvedPageHeight}
                initialPlaybackTime={playbackPositions[item.videoId]}
                hasNextEpisode={nextEpisode !== undefined}
                nextEpisodeLabel={nextEpisode?.episodeLabel}
                selectedPresentationType={selectedPresentationType}
                onChangePresentationType={handleChangePresentationType}
                onPlaybackPositionChange={handlePlaybackPositionChange}
                onPlayNextEpisode={() => handlePlayNextEpisode(index)}
                onOpenTheater={() => setOverlay("theater")}
                onOpenSeriesDetails={handleOpenSeriesDetails}
                onOpenStoryQaPage={handleOpenStoryQaPage}
              />
            );
          }}
          pagingEnabled
          showsVerticalScrollIndicator={false}
          bounces
          decelerationRate="fast"
          snapToInterval={resolvedPageHeight}
          snapToAlignment="start"
          disableIntervalMomentum
          onMomentumScrollEnd={handleMomentumScrollEnd}
          getItemLayout={(_, index) => ({
            length: resolvedPageHeight,
            offset: resolvedPageHeight * index,
            index
          })}
          onScrollToIndexFailed={(info) => {
            listRef.current?.scrollToOffset({ offset: resolvedPageHeight * info.index, animated: true });
          }}
          initialNumToRender={2}
          maxToRenderPerBatch={3}
          windowSize={3}
          removeClippedSubviews={false}
        />
      ) : null}
      {overlay === "theater" ? (
        <TheaterScreen seriesList={seriesList} onClose={() => setOverlay("none")} onPlaySeries={handlePlayVideo} />
      ) : null}
      {overlay === "seriesDetail" && selectedSeries ? (
        <SeriesDetailScreen
          series={selectedSeries}
          currentVideoId={videos[activeIndex]?.videoId}
          onBack={() => setOverlay("none")}
          onPlayEpisode={handlePlayVideo}
        />
      ) : null}
      {overlay === "storyQa" && storyQaContext ? (
        <StoryQaScreen video={storyQaContext.video} currentTime={storyQaContext.currentTime} onClose={() => setOverlay("none")} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#050505"
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
