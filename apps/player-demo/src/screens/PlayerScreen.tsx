import { useCallback, useEffect, useRef, useState } from "react";
import {
  FlatList,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  StyleSheet,
  Text,
  View
} from "react-native";
import { PlayerPage } from "../components/PlayerPage";
import { API_BASE_URL, API_REQUEST_TIMEOUT_MS } from "../config";
import { getFeedPageIndex } from "../domain/playerFeed";
import { loadPlayerVideos, PlayerVideo } from "../domain/playerApi";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { colors, radii, spacing } from "../theme";

function getSeriesKey(video: PlayerVideo) {
  if (video.seriesId) {
    return `id:${video.seriesId}`;
  }
  if (video.seriesName) {
    return `name:${video.seriesName}`;
  }
  return undefined;
}

function findNextEpisodeIndex(videos: PlayerVideo[], currentIndex: number) {
  const currentVideo = videos[currentIndex];
  if (!currentVideo) {
    return undefined;
  }
  const currentSeriesKey = getSeriesKey(currentVideo);
  if (!currentSeriesKey) {
    return undefined;
  }
  return videos.findIndex((video, index) => index > currentIndex && getSeriesKey(video) === currentSeriesKey);
}

export function PlayerScreen() {
  const [videos, setVideos] = useState<PlayerVideo[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [hasStartedFeed, setHasStartedFeed] = useState(false);
  const [pageHeight, setPageHeight] = useState(0);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<string | undefined>();
  const [selectedPresentationType, setSelectedPresentationType] = useState<InteractionPresentationType>("poll_bar");
  const listRef = useRef<FlatList<PlayerVideo>>(null);

  const fetchVideos = useCallback(async () => {
    setLoadState("loading");
    setLoadError(undefined);
    try {
      const nextVideos = await loadPlayerVideos({ apiBaseUrl: API_BASE_URL, timeoutMs: API_REQUEST_TIMEOUT_MS });
      setVideos(nextVideos);
      setActiveIndex(0);
      setHasStartedFeed(false);
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
          setHasStartedFeed(false);
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
        pageHeight,
        itemCount: videos.length
      });
      setActiveIndex(nextIndex);
    },
    [pageHeight, videos.length]
  );

  const handleChangePresentationType = useCallback((type: InteractionPresentationType) => {
    setSelectedPresentationType(type);
  }, []);

  const handlePlayNextEpisode = useCallback(
    (currentIndex: number) => {
      const nextIndex = findNextEpisodeIndex(videos, currentIndex);
      if (nextIndex === undefined || nextIndex < 0) {
        return;
      }
      setActiveIndex(nextIndex);
      setHasStartedFeed(true);
      listRef.current?.scrollToIndex({ index: nextIndex, animated: true });
    },
    [videos]
  );

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
        setPageHeight(event.nativeEvent.layout.height);
      }}
    >
      {pageHeight > 0 ? (
        <FlatList
          ref={listRef}
          data={videos}
          keyExtractor={(item) => item.videoId}
          renderItem={({ item, index }) => {
            const nextEpisodeIndex = findNextEpisodeIndex(videos, index);
            const nextEpisode =
              nextEpisodeIndex !== undefined && nextEpisodeIndex >= 0 ? videos[nextEpisodeIndex] : undefined;
            return (
              <PlayerPage
                video={item}
                isActive={index === activeIndex}
                shouldMountVideo={index === activeIndex}
                height={pageHeight}
                hasStartedFeed={hasStartedFeed}
                hasNextEpisode={nextEpisode !== undefined}
                nextEpisodeLabel={nextEpisode?.episodeLabel}
                selectedPresentationType={selectedPresentationType}
                onChangePresentationType={handleChangePresentationType}
                onStartFeed={() => setHasStartedFeed(true)}
                onPlayNextEpisode={() => handlePlayNextEpisode(index)}
              />
            );
          }}
          pagingEnabled
          showsVerticalScrollIndicator={false}
          bounces
          decelerationRate="fast"
          snapToInterval={pageHeight}
          snapToAlignment="start"
          disableIntervalMomentum
          onMomentumScrollEnd={handleMomentumScrollEnd}
          getItemLayout={(_, index) => ({ length: pageHeight, offset: pageHeight * index, index })}
          onScrollToIndexFailed={(info) => {
            listRef.current?.scrollToOffset({ offset: pageHeight * info.index, animated: true });
          }}
          initialNumToRender={1}
          maxToRenderPerBatch={2}
          windowSize={3}
          removeClippedSubviews={false}
        />
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
