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
import type { RoleCommerceFeedAd } from "../domain/roleCommerceAds";
import { resolveStoryQaContext } from "../domain/storyQa";
import {
  askWatchAssistant,
  type WatchAssistantToolCall,
  type WatchAssistantTranscription
} from "../domain/watchAssistant";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { HomeFeedPlaybackDebugPanel } from "./HomeFeedPlaybackDebugPanel";
import { PlayerBottomTabs } from "./PlayerBottomTabs";
import { PlayerPage, type WatchAssistantActionRequest } from "./PlayerPage";
import { PlayerTopBar } from "./PlayerTopBar";
import { RoleCommerceAdPage } from "./RoleCommerceAdPage";
import type { PlaybackRate } from "./SpeedSelector";
import { WatchAssistantPanel } from "./WatchAssistantPanel";

interface WatchAssistantPanelState {
  isOpen: boolean;
  message: string;
  reply?: string;
  error?: string;
  isLoading: boolean;
  voiceState: "idle" | "recording" | "transcribing";
  voiceMeta?: WatchAssistantTranscription;
  toolCalls: WatchAssistantToolCall[];
  executionHint?: string;
}

function resetWatchAssistantState(): WatchAssistantPanelState {
  return {
    isOpen: false,
    message: "",
    reply: undefined,
    error: undefined,
    isLoading: false,
    voiceState: "idle",
    voiceMeta: undefined,
    toolCalls: [],
    executionHint: undefined
  };
}

function isWebMicrophoneBlockedByInsecureOrigin(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const hostname = window.location.hostname;
  const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  return window.isSecureContext === false && !isLocalhost;
}

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
  roleCommerceAds = [],
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
  roleCommerceAds?: RoleCommerceFeedAd[];
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
    () => buildPlayerFeedItems({ videos, roleCommerceAds, mode }),
    [mode, roleCommerceAds, videos]
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
  const [selectedPlaybackRate, setSelectedPlaybackRate] = useState<PlaybackRate>(1);
  const [isSpeedMenuOpen, setIsSpeedMenuOpen] = useState(false);
  const [isAssistantInteractionBlocked, setIsAssistantInteractionBlocked] = useState(false);
  const [assistantState, setAssistantState] = useState<WatchAssistantPanelState>(() => resetWatchAssistantState());
  const [assistantActionRequest, setAssistantActionRequest] = useState<WatchAssistantActionRequest | undefined>();
  const listRef = useRef<FlatList<PlayerFeedItem>>(null);
  const bufferedPlaybackPositionRef = useRef<BufferedPlaybackPosition | undefined>(undefined);
  const assistantRequestRef = useRef(0);
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
  const isFeedScrollEnabled = getFeedScrollEnabled({
    isTimelineDragging: isTimelineDragging || isAssistantInteractionBlocked
  });
  const topBarItem = feedItems[visualActiveIndex] ?? feedItems[activeIndex];
  const topBarEpisodeLabel =
    topBarItem?.itemType === "video" ? topBarItem.video.episodeLabel : topBarItem?.itemType === "role_commerce_ad" ? "广告" : undefined;

  useEffect(() => {
    setSelectedPlaybackRate(1);
    setIsSpeedMenuOpen(false);
  }, [topBarItem?.itemId]);

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

  const getAssistantContextItem = useCallback(() => {
    const playbackItem = feedItems[playbackOwnerIndex];
    if (playbackItem?.itemType === "video") {
      return playbackItem;
    }
    const activeItem = feedItems[activeIndex];
    return activeItem?.itemType === "video" ? activeItem : undefined;
  }, [activeIndex, feedItems, playbackOwnerIndex]);

  const handleOpenWatchAssistant = useCallback(() => {
    setAssistantState((state) => ({ ...state, isOpen: true }));
  }, []);

  const handleAssistantActionApplied = useCallback((requestId: number, executionHint?: string) => {
    setAssistantActionRequest((current) => (current?.id === requestId ? undefined : current));
    if (executionHint) {
      setAssistantState((state) => ({ ...state, executionHint }));
    }
  }, []);

  const handleSubmitWatchAssistant = useCallback(
    (quickMessage?: string, inputMode: "text" | "voice" = "text", voiceMeta?: WatchAssistantTranscription) => {
      const nextMessage = (quickMessage ?? assistantState.message).trim();
      setAssistantState((state) => ({
        ...state,
        message: nextMessage,
        error: undefined,
        reply: undefined,
        voiceMeta,
        executionHint: undefined,
        toolCalls: []
      }));
      if (!nextMessage) {
        setAssistantState((state) => ({ ...state, error: "请输入指令或剧情问题" }));
        return;
      }

      const contextItem = getAssistantContextItem();
      if (!contextItem) {
        setAssistantState((state) => ({ ...state, error: "当前页面暂不支持陪看助手" }));
        return;
      }

      const context = resolveStoryQaContext(contextItem.video);
      const requestId = assistantRequestRef.current + 1;
      assistantRequestRef.current = requestId;
      setAssistantState((state) => ({ ...state, isLoading: true }));
      askWatchAssistant({
        apiBaseUrl: API_BASE_URL,
        message: nextMessage,
        seriesId: context.seriesId,
        videoId: contextItem.video.videoId,
        currentEpisode: context.currentEpisode,
        currentTime: playbackPositionsRef.current[contextItem.video.videoId] ?? 0,
        duration: contextItem.video.duration
      })
        .then((response) => {
          if (assistantRequestRef.current === requestId) {
            setAssistantState((state) => ({
              ...state,
              reply: response.reply,
              toolCalls: response.toolCalls
            }));
            setAssistantActionRequest({
              id: requestId,
              actions: response.actions,
              rawMessage: nextMessage,
              inputMode,
              voiceMeta
            });
          }
        })
        .catch((error: unknown) => {
          if (assistantRequestRef.current === requestId) {
            setAssistantState((state) => ({
              ...state,
              error: error instanceof Error ? error.message : "观看助手暂时不可用"
            }));
          }
        })
        .finally(() => {
          if (assistantRequestRef.current === requestId) {
            setAssistantState((state) => ({ ...state, isLoading: false }));
          }
        });
    },
    [assistantState.message, getAssistantContextItem]
  );

  const handleToggleVoiceRecording = useCallback(async () => {
    if (assistantState.isLoading) {
      return;
    }
    try {
      if (isWebMicrophoneBlockedByInsecureOrigin()) {
        throw new Error("当前页面不是 HTTPS，浏览器不会弹出麦克风授权。请使用 HTTPS 或本地 localhost 访问。");
      }
      await import("expo-audio");
      setAssistantState((state) => ({
        ...state,
        voiceState: "idle",
        error: "当前先用文本调试 Watch Assistant；语音录制留到 development build 阶段启用。"
      }));
    } catch (error) {
      setAssistantState((state) => ({
        ...state,
        voiceState: "idle",
        error:
          error instanceof Error && error.message.includes("HTTPS")
            ? error.message
            : "Expo Go 不包含 ExpoAudio 原生模块。当前先用文本调试，语音输入需要 development build。"
      }));
    }
  }, [assistantState.isLoading]);

  const handleCancelVoiceRecording = useCallback(() => {
    setAssistantState((state) => ({ ...state, voiceState: "idle" }));
  }, []);

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
          extraData={`${activeIndex}:${playbackOwnerIndex}:${visualActiveIndex}:${isFeedScrollEnabled}:${assistantActionRequest?.id ?? 0}`}
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
                playbackRate={selectedPlaybackRate}
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
                onOpenWatchAssistant={handleOpenWatchAssistant}
                assistantActionRequest={playbackPageState.shouldOwnPlayback ? assistantActionRequest : undefined}
                onAssistantActionApplied={handleAssistantActionApplied}
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
      <PlayerTopBar
        playbackRate={selectedPlaybackRate}
        isSpeedMenuOpen={isSpeedMenuOpen}
        onToggleSpeedMenu={() => setIsSpeedMenuOpen((open) => !open)}
        onSelectPlaybackRate={setSelectedPlaybackRate}
        mode={mode}
        episodeLabel={topBarEpisodeLabel}
        onBack={onBack}
      />
      <WatchAssistantPanel
        visible={assistantState.isOpen}
        message={assistantState.message}
        reply={assistantState.reply}
        error={assistantState.error}
        isLoading={assistantState.isLoading}
        voiceState={assistantState.voiceState}
        voiceDurationSec={0}
        toolCalls={assistantState.toolCalls}
        executionHint={assistantState.executionHint}
        onChangeMessage={(message) => setAssistantState((state) => ({ ...state, message }))}
        onSubmit={handleSubmitWatchAssistant}
        onToggleVoiceRecording={handleToggleVoiceRecording}
        onCancelVoiceRecording={handleCancelVoiceRecording}
        onInteractionBlockChange={setIsAssistantInteractionBlocked}
        onClose={() => setAssistantState((state) => ({ ...state, isOpen: false }))}
      />
      {mode === "home" ? (
        <PlayerBottomTabs activeTab="首页" presentation="docked" onPressTheater={onOpenTheater} />
      ) : null}
      {playbackObserver ? <HomeFeedPlaybackDebugPanel observer={playbackObserver} /> : null}
    </View>
  );
}
