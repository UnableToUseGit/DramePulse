import { useEvent } from "expo";
import { useVideoPlayer, VideoView } from "expo-video";
import { useEffect } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";

export interface SeekRequest {
  id: number;
  time: number;
}

export function VideoStage({
  isStarted,
  onStart,
  isPlaying,
  seekRequest,
  onTimeChange,
  streamUrl,
  showStartEntry = true
}: {
  isStarted: boolean;
  onStart: () => void;
  isPlaying: boolean;
  seekRequest: SeekRequest | undefined;
  onTimeChange: (time: number) => void;
  streamUrl: string;
  showStartEntry?: boolean;
}) {
  const player = useVideoPlayer(streamUrl, (instance) => {
    instance.loop = false;
    instance.timeUpdateEventInterval = 0.25;
  });
  const timeUpdate = useEvent(player, "timeUpdate", {
    currentTime: 0,
    currentLiveTimestamp: null,
    currentOffsetFromLive: null,
    bufferedPosition: 0
  });

  useEffect(() => {
    onTimeChange(timeUpdate?.currentTime ?? 0);
  }, [onTimeChange, timeUpdate?.currentTime]);

  useEffect(() => {
    if (isStarted && isPlaying) {
      player.play();
    } else {
      player.pause();
    }
  }, [isPlaying, isStarted, player]);

  useEffect(() => {
    if (seekRequest) {
      player.currentTime = seekRequest.time;
      onTimeChange(seekRequest.time);
    }
  }, [onTimeChange, player, seekRequest]);

  return (
    <View style={styles.root}>
      <VideoView
        style={styles.video}
        player={player}
        nativeControls={false}
        contentFit="cover"
        allowsFullscreen={false}
        allowsPictureInPicture={false}
      />
      {!isStarted && showStartEntry ? (
        <View style={styles.startOverlay}>
          <Pressable style={styles.startButton} onPress={onStart}>
            <Text style={styles.startButtonText}>点击播放短剧</Text>
          </Pressable>
          <Text style={styles.startHint}>DramePulse 即时互动 Demo</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#050505"
  },
  video: {
    width: "100%",
    height: "100%"
  },
  startOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(0,0,0,0.36)"
  },
  startButton: {
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: colors.accent
  },
  startButtonText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900"
  },
  startHint: {
    marginTop: spacing.md,
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700"
  }
});
