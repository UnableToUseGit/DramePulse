import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { DanmakuLayer } from "../components/DanmakuLayer";
import { PlaybackHint } from "../components/PlaybackHint";
import { PlayerControls } from "../components/PlayerControls";
import { PlayerChrome } from "../components/PlayerChrome";
import { SeekRequest, VideoStage } from "../components/VideoStage";
import { getDemoFixtures } from "../domain/fixtures";

export function PlayerScreen() {
  const fixtures = useMemo(() => getDemoFixtures(), []);
  const [currentTime, setCurrentTime] = useState(0);
  const [isStarted, setIsStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [seekVersion, setSeekVersion] = useState(0);

  const handleTimeChange = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  const handleStart = useCallback(() => {
    setIsStarted(true);
    setIsPlaying(true);
  }, []);

  const handleTogglePlay = useCallback(() => {
    if (!isStarted) {
      handleStart();
      return;
    }
    setIsPlaying((playing) => !playing);
  }, [handleStart, isStarted]);

  const handleSeekCommit = useCallback((time: number) => {
    setCurrentTime(time);
    setIsStarted(true);
    setSeekVersion((version) => version + 1);
    setSeekRequest({ id: Date.now(), time });
  }, []);

  return (
    <View style={styles.root}>
      <VideoStage
        isStarted={isStarted}
        isPlaying={isPlaying}
        seekRequest={seekRequest}
        onStart={handleStart}
        onTimeChange={handleTimeChange}
      />
      {isStarted ? (
        <DanmakuLayer
          currentTime={currentTime}
          danmaku={fixtures.danmaku}
          isPlaying={isPlaying}
          seekVersion={seekVersion}
        />
      ) : null}
      {isStarted ? <Pressable style={styles.tapLayer} onPress={handleTogglePlay} /> : null}
      <PlaybackHint isStarted={isStarted} isPlaying={isPlaying} />
      <PlayerChrome onToggleDebug={() => undefined} />
      <PlayerControls
        currentTime={currentTime}
        duration={120}
        onSeekCommit={handleSeekCommit}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#050505"
  },
  tapLayer: {
    ...StyleSheet.absoluteFillObject
  }
});
