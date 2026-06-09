import { useState } from "react";
import { PlayerFeed } from "../components/PlayerFeed";
import type { PlaybackAssetCache } from "../domain/playbackAssetCache";
import type { PlayerVideo } from "../domain/playerApi";
import type { InteractionPresentationType } from "../interaction-examples/types";

export function HomeFeedScreen({
  videos,
  playbackAssetCache,
  playbackPositions,
  onPlaybackPositionsChange,
  onInitialVideoPlaybackReady,
  onOpenTheater
}: {
  videos: PlayerVideo[];
  playbackAssetCache: PlaybackAssetCache;
  playbackPositions: Record<string, number>;
  onPlaybackPositionsChange: (positions: Record<string, number>) => void;
  onInitialVideoPlaybackReady?: () => void;
  onOpenTheater: () => void;
}) {
  const [selectedPresentationType, setSelectedPresentationType] = useState<InteractionPresentationType>("action_rail_candy");

  return (
    <PlayerFeed
      videos={videos}
      mode="home"
      playbackAssetCache={playbackAssetCache}
      playbackPositions={playbackPositions}
      selectedPresentationType={selectedPresentationType}
      onChangePresentationType={setSelectedPresentationType}
      onPlaybackPositionsChange={onPlaybackPositionsChange}
      onInitialVideoPlaybackReady={onInitialVideoPlaybackReady}
      onOpenTheater={onOpenTheater}
    />
  );
}
