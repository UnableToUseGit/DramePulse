import { useState } from "react";
import { PlayerFeed } from "../components/PlayerFeed";
import type { PlayerVideo } from "../domain/playerApi";
import type { InteractionPresentationType } from "../interaction-examples/types";

export function HomeFeedScreen({
  videos,
  playbackPositions,
  onPlaybackPositionsChange,
  onOpenTheater
}: {
  videos: PlayerVideo[];
  playbackPositions: Record<string, number>;
  onPlaybackPositionsChange: (positions: Record<string, number>) => void;
  onOpenTheater: () => void;
}) {
  const [selectedPresentationType, setSelectedPresentationType] = useState<InteractionPresentationType>("poll_bar");

  return (
    <PlayerFeed
      videos={videos}
      mode="home"
      playbackPositions={playbackPositions}
      selectedPresentationType={selectedPresentationType}
      onChangePresentationType={setSelectedPresentationType}
      onPlaybackPositionsChange={onPlaybackPositionsChange}
      onOpenTheater={onOpenTheater}
    />
  );
}
