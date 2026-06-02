import { useCallback, useMemo, useState } from "react";
import { PanResponder, StyleSheet, useWindowDimensions, View } from "react-native";
import { PlayerFeed } from "../components/PlayerFeed";
import { SeriesDetailSheet } from "../components/SeriesDetailSheet";
import { shouldStartEdgeBackSwipe, type SeriesGroup } from "../domain/playerFeed";
import type { PlayerVideo } from "../domain/playerApi";
import type { InteractionPresentationType } from "../interaction-examples/types";

export function SeriesPlayerScreen({
  series,
  initialVideoId,
  playbackPositions,
  onPlaybackPositionsChange,
  onBack,
  onResumeVideoChange
}: {
  series: SeriesGroup;
  initialVideoId?: string;
  playbackPositions: Record<string, number>;
  onPlaybackPositionsChange: (positions: Record<string, number>) => void;
  onBack: () => void;
  onResumeVideoChange: (seriesKey: string, videoId: string) => void;
}) {
  const [selectedPresentationType, setSelectedPresentationType] = useState<InteractionPresentationType>("poll_bar");
  const [isSeriesDetailVisible, setIsSeriesDetailVisible] = useState(false);
  const [currentVideoId, setCurrentVideoId] = useState(initialVideoId ?? series.episodes[0]?.videoId);
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

  return (
    <View style={styles.root}>
      <PlayerFeed
        key={`${series.seriesKey}:${currentVideoId ?? "first"}`}
        videos={series.episodes}
        mode="series"
        initialVideoId={currentVideoId}
        playbackPositions={playbackPositions}
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
