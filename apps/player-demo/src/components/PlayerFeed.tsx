import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FlatList, NativeScrollEvent, NativeSyntheticEvent, useWindowDimensions, View } from "react-native";
import { API_BASE_URL, ENABLE_PLAYBACK_DEBUG_PANEL } from "../config";
import { createHomeFeedPlaybackFileLogger } from "../domain/homeFeedPlaybackFileLogger";
import type { PlaybackAssetCache } from "../domain/playbackAssetCache";
import {
  type BufferedPlaybackPosition,
  buildPlayerFeedItems,
  findNextFeedItemIndex,
  flushBufferedPlaybackPosition,
  getFeedPageIndex,
  getFeedReleaseTargetIndex,
  getFeedScrollEnabled,
  getFeedVisualLayout,
  getRequestedVideoFeedIndex,
  getVideoIndexFromFeedItems,
  PlayerFeedItem,
  stagePlaybackPositionUpdate
} from "../domain/playerFeed";
import { getFeedPlaybackPageState } from "../domain/feedPlaybackCoordinator";
import {
  createHomeFeedPlaybackObserver,
  type HomeFeedPlaybackObserver
} from "../domain/homeFeedPlaybackObserver";
import type { PlayerVideo } from "../domain/playerApi";
import { DEMO_ROLE_COMMERCE_ADS } from "../domain/roleCommerceAds";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { HomeFeedPlaybackDebugPanel } from "./HomeFeedPlaybackDebugPanel";
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
  requestedVideoId,
  playbackAssetCache,
  playbackPositions,
  selectedPresentationType,
  seriesEpisodeCount,
  onChangePresentationType,
  onPlaybackPositionsChange,
  onActiveVideoChange,
  onInitialVideoPlaybackReady,
  onOpenTheater,
  onBack,
  onOpenSeriesDetail
}: {
  videos: PlayerVideo[];
  mode: "home" | "series";
  requestedVideoId?: string;
  playbackAssetCache: PlaybackAssetCache;
  playbackPositions: Record<string, number>;
  selectedPresentationType: InteractionPresentationType;
  seriesEpisodeCount?: number;
  onChangePresentationType: (type: InteractionPresentationType) => void;
  onPlaybackPositionsChange: (positions: Record<string, number>) => void;
  onActiveVideoChange?: (video: PlayerVideo) => void;
  onInitialVideoPlaybackReady?: () => void;
  onOpenTheater?: () => void;
  onBack?: () => void;
  onOpenSeriesDetail?: () => void;
}) {
  const feedItems = useMemo(
    () => buildPlayerFeedItems({ videos, roleCommerceAds: DEMO_ROLE_COMMERCE_ADS, mode }),
    [mode, videos]
  );
  const initialIndex = useMemo(
    () => getVideoIndexFromFeedItems(feedItems, requestedVideoId),
    [feedItems, requestedVideoId]
  );
  const [activeIndex, setActiveIndex] = useState(initialIndex);
  const [playbackOwnerIndex, setPlaybackOwnerIndex] = useState(initialIndex);
  const [visualActiveIndex, setVisualActiveIndex] = useState(initialIndex);
  const [pageHeight, setPageHeight] = useState(0);
  const [isTimelineDragging, setIsTimelineDragging] = useState(false);
  const listRef = useRef<FlatList<PlayerFeedItem>>(null);
  const bufferedPlaybackPositionRef = useRef<BufferedPlaybackPosition | undefined>(undefined);
  const isFeedDraggingRef = useRef(false);
  const playbackPositionsRef = useRef(playbackPositions);
  const visualActiveIndexRef = useRef(initialIndex);
  const previousRequestedVideoIdRef = useRef(requestedVideoId);
  const previousObservedActiveItemIdRef = useRef<string | undefined>(undefined);
  const previousObservedPlaybackOwnerItemIdRef = useRef<string | undefined>(undefined);
  const homeFeedPlaybackObserverRef = useRef<HomeFeedPlaybackObserver | undefined>(undefined);
  if (__DEV__ && ENABLE_PLAYBACK_DEBUG_PANEL && mode === "home" && homeFeedPlaybackObserverRef.current === undefined) {
    homeFeedPlaybackObserverRef.current = createHomeFeedPlaybackObserver({
      log: createHomeFeedPlaybackFileLogger({ apiBaseUrl: API_BASE_URL })
    });
  }
  const playbackObserver =
    __DEV__ && ENABLE_PLAYBACK_DEBUG_PANEL && mode === "home" ? homeFeedPlaybackObserverRef.current : undefined;
  const viewport = useWindowDimensions();
  const resolvedPageHeight = pageHeight > 0 ? pageHeight : viewport.height;
  const feedVisualLayout = getFeedVisualLayout({
    pageHeight: resolvedPageHeight,
    mode,
    hasSeriesEpisodeBar: mode === "series" && seriesEpisodeCount !== undefined
  });
  const isFeedScrollEnabled = getFeedScrollEnabled({ isTimelineDragging });

  useEffect(() => {
    playbackPositionsRef.current = playbackPositions;
  }, [playbackPositions]);

  const publishPlaybackPositions = useCallback(
    (nextPlaybackPositions: Record<string, number>) => {
      playbackPositionsRef.current = nextPlaybackPositions;
      onPlaybackPositionsChange(nextPlaybackPositions);
    },
    [onPlaybackPositionsChange]
  );

  const flushBufferedPosition = useCallback(() => {
    const staged = flushBufferedPlaybackPosition({
      bufferedPosition: bufferedPlaybackPositionRef.current,
      playbackPositions: playbackPositionsRef.current
    });
    bufferedPlaybackPositionRef.current = staged.bufferedPosition;
    if (staged.shouldPublish) {
      publishPlaybackPositions(staged.nextPlaybackPositions);
    }
  }, [publishPlaybackPositions]);

  const recordActiveItemChange = useCallback(
    (index: number) => {
      const item = feedItems[index];
      if (
        !playbackObserver ||
        item?.itemType !== "video" ||
        previousObservedActiveItemIdRef.current === item.itemId
      ) {
        return;
      }
      previousObservedActiveItemIdRef.current = item.itemId;
      playbackObserver.record({
        eventType: "feed_active_item_change",
        videoId: item.video.videoId,
        pageIndex: index,
        activeIndex: index
      });
    },
    [feedItems, playbackObserver]
  );

  const recordPlaybackOwnerChange = useCallback(
    (index: number, reason: string) => {
      const item = feedItems[index];
      if (
        !playbackObserver ||
        item?.itemType !== "video" ||
        previousObservedPlaybackOwnerItemIdRef.current === item.itemId
      ) {
        return;
      }
      previousObservedPlaybackOwnerItemIdRef.current = item.itemId;
      playbackObserver.record({
        eventType: "feed_playback_owner_change",
        videoId: item.video.videoId,
        pageIndex: index,
        activeIndex: index,
        details: { reason }
      });
    },
    [feedItems, playbackObserver]
  );

  const handleSetPlaybackOwnerIndex = useCallback(
    (index: number, reason: string) => {
      recordPlaybackOwnerChange(index, reason);
      setPlaybackOwnerIndex(index);
    },
    [recordPlaybackOwnerChange]
  );

  const handleSetVisualActiveIndex = useCallback((index: number) => {
    if (visualActiveIndexRef.current === index) {
      return;
    }
    visualActiveIndexRef.current = index;
    setVisualActiveIndex(index);
  }, []);

  const handleSetActiveIndex = useCallback(
    (index: number) => {
      recordActiveItemChange(index);
      setActiveIndex(index);
      const item = feedItems[index];
      if (item?.itemType === "video") {
        onActiveVideoChange?.(item.video);
      }
    },
    [feedItems, onActiveVideoChange, recordActiveItemChange]
  );

  useEffect(() => {
    recordActiveItemChange(activeIndex);
  }, [activeIndex, recordActiveItemChange]);

  useEffect(() => {
    recordPlaybackOwnerChange(playbackOwnerIndex, "initial");
  }, [playbackOwnerIndex, recordPlaybackOwnerChange]);

  useEffect(() => {
    const previousRequestedVideoId = previousRequestedVideoIdRef.current;
    previousRequestedVideoIdRef.current = requestedVideoId;
    const requestedIndex = getRequestedVideoFeedIndex({
      items: feedItems,
      previousRequestedVideoId,
      requestedVideoId,
      activeIndex
    });
    if (requestedIndex === undefined) {
      return;
    }
    handleSetActiveIndex(requestedIndex);
    handleSetPlaybackOwnerIndex(requestedIndex, "requested_video");
    handleSetVisualActiveIndex(requestedIndex);
    listRef.current?.scrollToIndex({ index: requestedIndex, animated: false });
  }, [
    activeIndex,
    feedItems,
    handleSetActiveIndex,
    handleSetPlaybackOwnerIndex,
    handleSetVisualActiveIndex,
    requestedVideoId
  ]);

  const handleMomentumScrollEnd = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      isFeedDraggingRef.current = false;
      flushBufferedPosition();
      playbackObserver?.record({
        eventType: "feed_scroll_end",
        activeIndex,
        details: { offsetY: event.nativeEvent.contentOffset.y }
      });
      const nextIndex = getFeedPageIndex({
        offsetY: event.nativeEvent.contentOffset.y,
        pageHeight: resolvedPageHeight,
        itemCount: feedItems.length
      });
      handleSetVisualActiveIndex(nextIndex);
      handleSetActiveIndex(nextIndex);
      handleSetPlaybackOwnerIndex(nextIndex, "momentum_end");
    },
    [
      activeIndex,
      feedItems.length,
      flushBufferedPosition,
      handleSetActiveIndex,
      handleSetPlaybackOwnerIndex,
      handleSetVisualActiveIndex,
      playbackObserver,
      resolvedPageHeight
    ]
  );

  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const nextVisualIndex = getFeedPageIndex({
        offsetY: event.nativeEvent.contentOffset.y,
        pageHeight: resolvedPageHeight,
        itemCount: feedItems.length
      });
      handleSetVisualActiveIndex(nextVisualIndex);
    },
    [feedItems.length, handleSetVisualActiveIndex, resolvedPageHeight]
  );

  const handleScrollBeginDrag = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      isFeedDraggingRef.current = true;
      playbackObserver?.record({
        eventType: "feed_scroll_begin",
        activeIndex,
        details: { offsetY: event.nativeEvent.contentOffset.y }
      });
    },
    [activeIndex, playbackObserver]
  );

  const handleScrollEndDrag = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const nativeEvent = event.nativeEvent as NativeScrollEvent & {
        targetContentOffset?: { y?: number };
        velocity?: { y?: number };
      };
      const targetIndex = getFeedReleaseTargetIndex({
        activeIndex,
        itemCount: feedItems.length,
        offsetY: nativeEvent.contentOffset.y,
        pageHeight: resolvedPageHeight,
        targetOffsetY: nativeEvent.targetContentOffset?.y,
        velocityY: nativeEvent.velocity?.y
      });
      playbackObserver?.record({
        eventType: "feed_scroll_release",
        activeIndex,
        details: {
          offsetY: nativeEvent.contentOffset.y,
          targetIndex,
          targetOffsetY: nativeEvent.targetContentOffset?.y,
          velocityY: nativeEvent.velocity?.y
        }
      });
      handleSetVisualActiveIndex(targetIndex);
      handleSetPlaybackOwnerIndex(targetIndex, "drag_release");
    },
    [
      activeIndex,
      feedItems.length,
      handleSetPlaybackOwnerIndex,
      handleSetVisualActiveIndex,
      playbackObserver,
      resolvedPageHeight
    ]
  );

  const handlePlayNextItem = useCallback(
    (currentIndex: number) => {
      const nextIndex = findNextFeedItemIndex(feedItems, currentIndex);
      if (nextIndex === undefined) {
        return;
      }
      handleSetActiveIndex(nextIndex);
      handleSetPlaybackOwnerIndex(nextIndex, "play_next_item");
      handleSetVisualActiveIndex(nextIndex);
      listRef.current?.scrollToIndex({ index: nextIndex, animated: true });
    },
    [feedItems, handleSetActiveIndex, handleSetPlaybackOwnerIndex, handleSetVisualActiveIndex]
  );

  const handlePlaybackPositionChange = useCallback(
    (videoId: string, time: number) => {
      const staged = stagePlaybackPositionUpdate({
        isFeedDragging: isFeedDraggingRef.current,
        playbackPositions: playbackPositionsRef.current,
        videoId,
        time
      });
      if (isFeedDraggingRef.current) {
        if (staged.bufferedPosition) {
          bufferedPlaybackPositionRef.current = staged.bufferedPosition;
        }
        return;
      }
      bufferedPlaybackPositionRef.current = staged.bufferedPosition;
      if (staged.shouldPublish) {
        publishPlaybackPositions(staged.nextPlaybackPositions);
      }
    },
    [publishPlaybackPositions]
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
          data={feedItems}
          initialScrollIndex={initialIndex}
          extraData={`${activeIndex}:${playbackOwnerIndex}:${visualActiveIndex}:${isFeedScrollEnabled}`}
          keyExtractor={(item) => item.itemId}
          renderItem={({ item, index }) => {
            const playbackPageState = getFeedPlaybackPageState({
              item,
              pageIndex: index,
              activeIndex: playbackOwnerIndex,
              playbackPositions
            });
            const visualPageState = getFeedPlaybackPageState({
              item,
              pageIndex: index,
              activeIndex: visualActiveIndex,
              playbackPositions
            });
            const nextItem = feedItems[index + 1];
            const nextItemLabel = getNextItemLabel(nextItem);
            if (item.itemType === "role_commerce_ad") {
              return (
                <RoleCommerceAdPage
                  ad={item.ad}
                  height={resolvedPageHeight}
                  videoHeight={feedVisualLayout.videoHeight}
                  controlsBottomOffset={feedVisualLayout.controlsBottomOffset}
                  metaBottomOffset={feedVisualLayout.metaBottomOffset}
                  isActive={playbackPageState.shouldOwnPlayback}
                  hasNextItem={nextItem !== undefined}
                  nextItemLabel={nextItemLabel}
                  seriesEpisodeCount={seriesEpisodeCount}
                  onBack={onBack}
                  onOpenSeriesDetail={onOpenSeriesDetail}
                />
              );
            }
            return (
              <PlayerPage
                video={item.video}
                pageIndex={index}
                playbackAssetCache={playbackAssetCache}
                playbackObserver={playbackObserver}
                isActive={playbackPageState.shouldOwnPlayback}
                pageRole={playbackPageState.pageRole}
                visualPageRole={visualPageState.pageRole}
                height={resolvedPageHeight}
                videoHeight={feedVisualLayout.videoHeight}
                controlsBottomOffset={feedVisualLayout.controlsBottomOffset}
                metaBottomOffset={feedVisualLayout.metaBottomOffset}
                actionRailBottomOffset={feedVisualLayout.actionRailBottomOffset}
                resumePlaybackTime={playbackPageState.resumeTime}
                hasNextEpisode={nextItem !== undefined}
                nextEpisodeLabel={nextItemLabel}
                selectedPresentationType={selectedPresentationType}
                onChangePresentationType={onChangePresentationType}
                onPlaybackPositionChange={handlePlaybackPositionChange}
                onTimelineDragStateChange={setIsTimelineDragging}
                onPlaybackReady={
                  mode === "home" && index === initialIndex ? onInitialVideoPlaybackReady : undefined
                }
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
          onScrollBeginDrag={handleScrollBeginDrag}
          onScroll={handleScroll}
          onScrollEndDrag={handleScrollEndDrag}
          onMomentumScrollEnd={handleMomentumScrollEnd}
          scrollEventThrottle={64}
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
      {playbackObserver ? <HomeFeedPlaybackDebugPanel observer={playbackObserver} /> : null}
    </View>
  );
}
