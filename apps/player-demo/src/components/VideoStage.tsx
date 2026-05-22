import { useEvent } from "expo";
import { useVideoPlayer, VideoView } from "expo-video";
import { useEffect } from "react";
import { StyleSheet, View } from "react-native";

const videoSource = require("../../assets/video/ep01.mp4");

export function VideoStage({ onTimeChange }: { onTimeChange: (time: number) => void }) {
  const player = useVideoPlayer(videoSource, (instance) => {
    instance.loop = false;
    instance.timeUpdateEventInterval = 0.25;
    instance.play();
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
  }
});
