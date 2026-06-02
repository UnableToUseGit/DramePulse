import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FlatList, NativeScrollEvent, NativeSyntheticEvent, useWindowDimensions, View } from "react-native";
import {
  findNextEpisodeIndex,
  getFeedPageIndex,
  getFeedScrollEnabled,
  getVideoIndex,
  shouldPreloadFeedPage
} from "../domain/playerFeed";
import type { PlayerVideo } from "../domain/playerApi";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { PlayerPage } from "./PlayerPage";

export function PlayerFeed({
  videos,
  mode,
  initialVideoId,
  playbackPositions,
  selectedPresentationType,
  seriesEpisodeCount,
  onChangePresentationType,
  onPlaybackPositionsChange,
  onActiveVideoChange,
  onOpenTheater,
  onBack,
  onOpenSeriesDetail
}: {
  videos: PlayerVideo[];
  mode: "home" | "series";
  initialVideoId?: string;
  playbackPositions: Record<string, number>;
  selectedPresentationType: InteractionPresentationType;
  seriesEpisodeCount?: number;
  onChangePresentationType: (type: InteractionPresentationType) => void;
  onPlaybackPositionsChange: (positions: Record<string, number>) => void;
  onActiveVideoChange?: (video: PlayerVideo) => void;
  onOpenTheater?: () => void;
  onBack?: () => void;
  onOpenSeriesDetail?: () => void;
}) {
  const initialIndex = useMemo(() => getVideoIndex(videos, initialVideoId), [initialVideoId, videos]);
  const [activeIndex, setActiveIndex] = useState(initialIndex);
  const [pageHeight, setPageHeight] = useState(0);
  const [isTimelineDragging, setIsTimelineDragging] = useState(false);
  const listRef = useRef<FlatList<PlayerVideo>>(null);
  const viewport = useWindowDimensions();
  const resolvedPageHeight = pageHeight > 0 ? pageHeight : viewport.height;
  const isFeedScrollEnabled = getFeedScrollEnabled({ isTimelineDragging });

  useEffect(() => {
    setActiveIndex(initialIndex);
    if (resolvedPageHeight > 0 && videos.length > 0) {
      listRef.current?.scrollToIndex({ index: initialIndex, animated: false });
    }
  }, [initialIndex, resolvedPageHeight, videos.length]);

  const handleSetActiveIndex = useCallback(
    (index: number) => {
      setActiveIndex(index);
      const video = videos[index];
      if (video) {
        onActiveVideoChange?.(video);
      }
    },
    [onActiveVideoChange, videos]
  );

  const handleMomentumScrollEnd = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const nextIndex = getFeedPageIndex({
        offsetY: event.nativeEvent.contentOffset.y,
        pageHeight: resolvedPageHeight,
        itemCount: videos.length
      });
      handleSetActiveIndex(nextIndex);
    },
    [handleSetActiveIndex, resolvedPageHeight, videos.length]
  );

  const handlePlayNextEpisode = useCallback(
    (currentIndex: number) => {
      const nextIndex = findNextEpisodeIndex(videos, currentIndex);
      if (nextIndex === undefined) {
        return;
      }
      handleSetActiveIndex(nextIndex);
      listRef.current?.scrollToIndex({ index: nextIndex, animated: true });
    },
    [handleSetActiveIndex, videos]
  );

  const handlePlaybackPositionChange = useCallback(
    (videoId: string, time: number) => {
      if (playbackPositions[videoId] === time) {
        return;
      }
      onPlaybackPositionsChange({
        ...playbackPositions,
        [videoId]: time
      });
    },
    [onPlaybackPositionsChange, playbackPositions]
  );

  const scrollToVideo = useCallback(
    (video: PlayerVideo) => {
      const index = videos.findIndex((item) => item.videoId === video.videoId);
      if (index < 0) {
        return;
      }
      handleSetActiveIndex(index);
      listRef.current?.scrollToIndex({ index, animated: false });
    },
    [handleSetActiveIndex, videos]
  );

  return (
    <View
      style={{ flex: 1, backgroundColor: "#050505" }}
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
          initialScrollIndex={initialIndex}
          extraData={`${activeIndex}:${isFeedScrollEnabled}`}
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
                onChangePresentationType={onChangePresentationType}
                onPlaybackPositionChange={handlePlaybackPositionChange}
                onTimelineDragStateChange={setIsTimelineDragging}
                onPlayNextEpisode={() => handlePlayNextEpisode(index)}
                mode={mode}
                seriesEpisodeCount={seriesEpisodeCount}
                onOpenTheater={onOpenTheater}
                onBack={onBack}
                onOpenSeriesDetail={onOpenSeriesDetail}
              />
            );
          }}
          pagingEnabled
          scrollEnabled={isFeedScrollEnabled}
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
    </View>
  );
}
