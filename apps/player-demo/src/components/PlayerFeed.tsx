import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FlatList, NativeScrollEvent, NativeSyntheticEvent, useWindowDimensions, View } from "react-native";
import {
  buildPlayerFeedItems,
  findNextFeedItemIndex,
  getFeedPageIndex,
  getFeedScrollEnabled,
  getVideoIndexFromFeedItems,
  PlayerFeedItem,
  shouldPreloadFeedPage
} from "../domain/playerFeed";
import type { PlayerVideo } from "../domain/playerApi";
import { DEMO_ROLE_COMMERCE_ADS } from "../domain/roleCommerceAds";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { PlayerPage } from "./PlayerPage";
import { RoleCommerceAdPage } from "./RoleCommerceAdPage";

function getNextItemLabel(item: PlayerFeedItem | undefined) {
  if (item?.itemType === "video") {
    return item.video.episodeLabel;
  }
  if (item?.itemType === "role_commerce_ad") {
    return "广告";
  }
  return undefined;
}

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
  const feedItems = useMemo(
    () => buildPlayerFeedItems({ videos, roleCommerceAds: DEMO_ROLE_COMMERCE_ADS, mode }),
    [mode, videos]
  );
  const initialIndex = useMemo(() => getVideoIndexFromFeedItems(feedItems, initialVideoId), [feedItems, initialVideoId]);
  const [activeIndex, setActiveIndex] = useState(initialIndex);
  const [pageHeight, setPageHeight] = useState(0);
  const [isTimelineDragging, setIsTimelineDragging] = useState(false);
  const listRef = useRef<FlatList<PlayerFeedItem>>(null);
  const viewport = useWindowDimensions();
  const resolvedPageHeight = pageHeight > 0 ? pageHeight : viewport.height;
  const isFeedScrollEnabled = getFeedScrollEnabled({ isTimelineDragging });

  useEffect(() => {
    setActiveIndex(initialIndex);
    if (resolvedPageHeight > 0 && feedItems.length > 0) {
      listRef.current?.scrollToIndex({ index: initialIndex, animated: false });
    }
  }, [feedItems.length, initialIndex, resolvedPageHeight]);

  const handleSetActiveIndex = useCallback(
    (index: number) => {
      setActiveIndex(index);
      const item = feedItems[index];
      if (item?.itemType === "video") {
        onActiveVideoChange?.(item.video);
      }
    },
    [feedItems, onActiveVideoChange]
  );

  const handleMomentumScrollEnd = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const nextIndex = getFeedPageIndex({
        offsetY: event.nativeEvent.contentOffset.y,
        pageHeight: resolvedPageHeight,
        itemCount: feedItems.length
      });
      handleSetActiveIndex(nextIndex);
    },
    [feedItems.length, handleSetActiveIndex, resolvedPageHeight]
  );

  const handlePlayNextItem = useCallback(
    (currentIndex: number) => {
      const nextIndex = findNextFeedItemIndex(feedItems, currentIndex);
      if (nextIndex === undefined) {
        return;
      }
      handleSetActiveIndex(nextIndex);
      listRef.current?.scrollToIndex({ index: nextIndex, animated: true });
    },
    [feedItems, handleSetActiveIndex]
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
      const index = feedItems.findIndex((item) => item.itemType === "video" && item.video.videoId === video.videoId);
      if (index < 0) {
        return;
      }
      handleSetActiveIndex(index);
      listRef.current?.scrollToIndex({ index, animated: false });
    },
    [feedItems, handleSetActiveIndex]
  );

  void scrollToVideo;

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
          data={feedItems}
          initialScrollIndex={initialIndex}
          extraData={`${activeIndex}:${isFeedScrollEnabled}`}
          keyExtractor={(item) => item.itemId}
          renderItem={({ item, index }) => {
            const nextItem = feedItems[index + 1];
            const nextItemLabel = getNextItemLabel(nextItem);
            if (item.itemType === "role_commerce_ad") {
              return (
                <RoleCommerceAdPage
                  ad={item.ad}
                  height={resolvedPageHeight}
                  isActive={index === activeIndex}
                  hasNextItem={nextItem !== undefined}
                  nextItemLabel={nextItemLabel}
                  onPlayNextItem={() => handlePlayNextItem(index)}
                />
              );
            }
            return (
              <PlayerPage
                video={item.video}
                isActive={index === activeIndex}
                shouldMountVideo={shouldPreloadFeedPage({ pageIndex: index, activeIndex })}
                height={resolvedPageHeight}
                initialPlaybackTime={playbackPositions[item.video.videoId]}
                hasNextEpisode={nextItem !== undefined}
                nextEpisodeLabel={nextItemLabel}
                selectedPresentationType={selectedPresentationType}
                onChangePresentationType={onChangePresentationType}
                onPlaybackPositionChange={handlePlaybackPositionChange}
                onTimelineDragStateChange={setIsTimelineDragging}
                onPlayNextEpisode={() => handlePlayNextItem(index)}
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
