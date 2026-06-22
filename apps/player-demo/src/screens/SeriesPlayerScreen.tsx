import { useCallback, useEffect, useMemo, useState } from "react";
import { PanResponder, StyleSheet, useWindowDimensions, View } from "react-native";
import { PlayerFeed } from "../components/PlayerFeed";
import { SeriesDetailSheet } from "../components/SeriesDetailSheet";
import { API_BASE_URL } from "../config";
import type { PlaybackAssetCache } from "../domain/playbackAssetCache";
import { shouldStartEdgeBackSwipe, type SeriesGroup } from "../domain/playerFeed";
import type { PlayerVideo } from "../domain/playerApi";
import { loadSeriesAdSlots } from "../domain/playerDataApi";
import type { RoleCommerceFeedAd } from "../domain/roleCommerceAds";
import type { InteractionPresentationType } from "../interaction-examples/types";

export function SeriesPlayerScreen({
  series,
  initialVideoId,
  playbackAssetCache,
  playbackPositions,
  onPlaybackPositionsChange,
  onBack,
  onResumeVideoChange
}: {
  series: SeriesGroup;
  initialVideoId?: string;
  playbackAssetCache: PlaybackAssetCache;
  playbackPositions: Record<string, number>;
  onPlaybackPositionsChange: (positions: Record<string, number>) => void;
  onBack: () => void;
  onResumeVideoChange: (seriesKey: string, videoId: string) => void;
}) {
  const [selectedPresentationType, setSelectedPresentationType] = useState<InteractionPresentationType>("action_rail_candy");
  const [isSeriesDetailVisible, setIsSeriesDetailVisible] = useState(false);
  const [currentVideoId, setCurrentVideoId] = useState(initialVideoId ?? series.episodes[0]?.videoId);
  const [roleCommerceAds, setRoleCommerceAds] = useState<RoleCommerceFeedAd[]>([]);
  const viewport = useWindowDimensions();
  const edgeBackSwipeResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, gestureState) =>
          shouldStartEdgeBackSwipe({
            startX: gestureState.x0,
            startY: gestureState.y0,
            screenHeight: viewport.height,
            deltaX: gestureState.dx,
            deltaY: gestureState.dy
          }),
        onPanResponderRelease: (_, gestureState) => {
          if (gestureState.dx > 72) {
            onBack();
          }
        }
      }),
    [onBack, viewport.height]
  );

  const handleActiveVideoChange = useCallback(
    (video: PlayerVideo) => {
      setCurrentVideoId(video.videoId);
      onResumeVideoChange(series.seriesKey, video.videoId);
    },
    [onResumeVideoChange, series.seriesKey]
  );

  const handleSelectEpisode = useCallback(
    (video: PlayerVideo) => {
      setCurrentVideoId(video.videoId);
      onResumeVideoChange(series.seriesKey, video.videoId);
      setIsSeriesDetailVisible(false);
    },
    [onResumeVideoChange, series.seriesKey]
  );

  useEffect(() => {
    let cancelled = false;
    const seriesId = series.coverVideo.seriesId;
    if (!seriesId) {
      setRoleCommerceAds([]);
      return () => {
        cancelled = true;
      };
    }
    loadSeriesAdSlots({ apiBaseUrl: API_BASE_URL, seriesId })
      .then((ads) => {
        if (!cancelled) {
          setRoleCommerceAds(ads);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRoleCommerceAds([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [series.coverVideo.seriesId]);

  return (
    <View style={styles.root}>
      <PlayerFeed
        videos={series.episodes}
        mode="series"
        requestedVideoId={currentVideoId}
        playbackAssetCache={playbackAssetCache}
        playbackPositions={playbackPositions}
        roleCommerceAds={roleCommerceAds}
        selectedPresentationType={selectedPresentationType}
        seriesEpisodeCount={series.episodeCount}
        onChangePresentationType={setSelectedPresentationType}
        onPlaybackPositionsChange={onPlaybackPositionsChange}
        onActiveVideoChange={handleActiveVideoChange}
        onBack={onBack}
        onOpenSeriesDetail={() => setIsSeriesDetailVisible(true)}
      />
      <SeriesDetailSheet
        visible={isSeriesDetailVisible}
        series={series}
        currentVideoId={currentVideoId}
        onClose={() => setIsSeriesDetailVisible(false)}
        onSelectEpisode={handleSelectEpisode}
      />
      <View
        pointerEvents="box-only"
        style={[styles.edgeBackSwipeZone, { bottom: 96 }]}
        {...edgeBackSwipeResponder.panHandlers}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#050505"
  },
  edgeBackSwipeZone: {
    position: "absolute",
    left: 0,
    top: 0,
    width: 28
  }
});
