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
  onInitialVideoFirstFrameRender,
  onOpenTheater
}: {
  videos: PlayerVideo[];
  playbackAssetCache: PlaybackAssetCache;
  playbackPositions: Record<string, number>;
  onPlaybackPositionsChange: (positions: Record<string, number>) => void;
  onInitialVideoFirstFrameRender?: () => void;
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
      onInitialVideoFirstFrameRender={onInitialVideoFirstFrameRender}
      onOpenTheater={onOpenTheater}
    />
  );
}
