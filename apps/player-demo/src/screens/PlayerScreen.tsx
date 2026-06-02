import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { API_BASE_URL, API_REQUEST_TIMEOUT_MS } from "../config";
import {
  findNextEpisodeIndex,
  getFeedPageIndex,
  getFeedScrollEnabled,
  getNextEpisodeInfoByIndex,
  shouldPreloadFeedPage
} from "../domain/playerFeed";
import { loadPlayerVideos, PlayerVideo } from "../domain/playerApi";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { colors, radii, spacing } from "../theme";

export function PlayerScreen() {
  const [videos, setVideos] = useState<PlayerVideo[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [pageHeight, setPageHeight] = useState(0);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<string | undefined>();
  const [selectedPresentationType, setSelectedPresentationType] = useState<InteractionPresentationType>("poll_bar");
  const [isTimelineDragging, setIsTimelineDragging] = useState(false);
  const listRef = useRef<FlatList<PlayerVideo>>(null);
  const playbackPositionsRef = useRef<Record<string, number>>({});
  const viewport = useWindowDimensions();
  const resolvedPageHeight = pageHeight > 0 ? pageHeight : viewport.height;
  const nextEpisodeInfoByIndex = useMemo(() => getNextEpisodeInfoByIndex(videos), [videos]);
  const feedScrollEnabled = getFeedScrollEnabled({ isTimelineDragging });

  const fetchVideos = useCallback(async () => {
    setLoadState("loading");
    setLoadError(undefined);
    try {
      const nextVideos = await loadPlayerVideos({ apiBaseUrl: API_BASE_URL, timeoutMs: API_REQUEST_TIMEOUT_MS });
      setVideos(nextVideos);
      setActiveIndex(0);
      playbackPositionsRef.current = {};
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
          playbackPositionsRef.current = {};
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

  const handlePlaybackPositionChange = useCallback((videoId: string, time: number) => {
    playbackPositionsRef.current[videoId] = time;
  }, []);

  const renderPlayerPage = useCallback(
    ({ item, index }: { item: PlayerVideo; index: number }) => {
      const nextEpisodeInfo = nextEpisodeInfoByIndex[index];
      return (
        <PlayerFeedItem
          video={item}
          index={index}
          activeIndex={activeIndex}
          pageHeight={resolvedPageHeight}
          initialPlaybackTime={playbackPositionsRef.current[item.videoId]}
          hasNextEpisode={nextEpisodeInfo?.hasNextEpisode ?? false}
          nextEpisodeLabel={nextEpisodeInfo?.nextEpisodeLabel}
          selectedPresentationType={selectedPresentationType}
          onChangePresentationType={handleChangePresentationType}
          onPlaybackPositionChange={handlePlaybackPositionChange}
          onTimelineDragStateChange={setIsTimelineDragging}
          onPlayNextEpisode={handlePlayNextEpisode}
        />
      );
    },
    [
      activeIndex,
      handleChangePresentationType,
      handlePlayNextEpisode,
      handlePlaybackPositionChange,
      nextEpisodeInfoByIndex,
      resolvedPageHeight,
      selectedPresentationType
    ]
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
          renderItem={renderPlayerPage}
          pagingEnabled
          showsVerticalScrollIndicator={false}
          bounces
          scrollEnabled={feedScrollEnabled}
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
    </View>
  );
}

const PlayerFeedItem = memo(function PlayerFeedItem({
  video,
  index,
  activeIndex,
  pageHeight,
  initialPlaybackTime,
  hasNextEpisode,
  nextEpisodeLabel,
  selectedPresentationType,
  onChangePresentationType,
  onPlaybackPositionChange,
  onTimelineDragStateChange,
  onPlayNextEpisode
}: {
  video: PlayerVideo;
  index: number;
  activeIndex: number;
  pageHeight: number;
  initialPlaybackTime?: number;
  hasNextEpisode: boolean;
  nextEpisodeLabel?: string;
  selectedPresentationType: InteractionPresentationType;
  onChangePresentationType: (type: InteractionPresentationType) => void;
  onPlaybackPositionChange: (videoId: string, time: number) => void;
  onTimelineDragStateChange: (isDragging: boolean) => void;
  onPlayNextEpisode: (currentIndex: number) => void;
}) {
  const handlePlayNextEpisode = useCallback(() => {
    onPlayNextEpisode(index);
  }, [index, onPlayNextEpisode]);
  return (
    <PlayerPage
      video={video}
      isActive={index === activeIndex}
      shouldMountVideo={shouldPreloadFeedPage({ pageIndex: index, activeIndex })}
      height={pageHeight}
      initialPlaybackTime={initialPlaybackTime}
      hasNextEpisode={hasNextEpisode}
      nextEpisodeLabel={nextEpisodeLabel}
      selectedPresentationType={selectedPresentationType}
      onChangePresentationType={onChangePresentationType}
      onPlaybackPositionChange={onPlaybackPositionChange}
      onTimelineDragStateChange={onTimelineDragStateChange}
      onPlayNextEpisode={handlePlayNextEpisode}
    />
  );
});

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
