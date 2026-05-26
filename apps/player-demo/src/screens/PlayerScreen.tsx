import { useCallback, useEffect, useState } from "react";
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
import { API_BASE_URL } from "../config";
import { getFeedPageIndex } from "../domain/playerFeed";
import { loadPlayerVideos, PlayerVideo } from "../domain/playerApi";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { colors, radii, spacing } from "../theme";

export function PlayerScreen() {
  const [videos, setVideos] = useState<PlayerVideo[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [hasStartedFeed, setHasStartedFeed] = useState(false);
  const [pageHeight, setPageHeight] = useState(0);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<string | undefined>();
  const [selectedPresentationType, setSelectedPresentationType] = useState<InteractionPresentationType>("poll_bar");
  const viewport = useWindowDimensions();
  const resolvedPageHeight = pageHeight > 0 ? pageHeight : viewport.height;

  const fetchVideos = useCallback(async () => {
    setLoadState("loading");
    setLoadError(undefined);
    try {
      const nextVideos = await loadPlayerVideos({ apiBaseUrl: API_BASE_URL });
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
    loadPlayerVideos({ apiBaseUrl: API_BASE_URL })
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
      setActiveIndex(
        getFeedPageIndex({
          offsetY: event.nativeEvent.contentOffset.y,
          pageHeight: resolvedPageHeight,
          itemCount: videos.length
        })
      );
    },
    [resolvedPageHeight, videos.length]
  );

  const handleChangePresentationType = useCallback((type: InteractionPresentationType) => {
    setSelectedPresentationType(type);
  }, []);

  if (loadState === "loading") {
    return (
      <View style={[styles.root, styles.centerState]}>
        <Text style={styles.stateTitle}>正在连接后端视频源</Text>
        <Text style={styles.stateText}>GET {API_BASE_URL}/api/videos</Text>
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
          data={videos}
          keyExtractor={(item) => item.videoId}
          renderItem={({ item, index }) => (
            <PlayerPage
              video={item}
              isActive={index === activeIndex}
              height={resolvedPageHeight}
              hasStartedFeed={hasStartedFeed}
              selectedPresentationType={selectedPresentationType}
              onChangePresentationType={handleChangePresentationType}
              onStartFeed={() => setHasStartedFeed(true)}
            />
          )}
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
          initialNumToRender={1}
          maxToRenderPerBatch={2}
          windowSize={3}
          removeClippedSubviews
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
