import { StyleSheet, Text, View } from "react-native";
import type { DanmakuItem } from "../domain/types";

const LANES = [78, 112, 146, 180, 214];

export function DanmakuLayer({ currentTime, danmaku }: { currentTime: number; danmaku: DanmakuItem[] }) {
  const visible = danmaku.filter((item) => item.time_sec <= currentTime && currentTime - item.time_sec < 4).slice(-8);

  return (
    <View pointerEvents="none" style={styles.root}>
      {visible.map((item, index) => {
        const age = Math.max(0, currentTime - item.time_sec);
        const lane = LANES[index % LANES.length];
        return (
          <Text
            key={`${item.danmaku_id ?? item.time_sec}-${index}`}
            numberOfLines={1}
            style={[
              styles.text,
              {
                top: lane,
                right: `${Math.min(88, age * 24)}%`,
                opacity: Math.max(0.15, 1 - age / 4)
              }
            ]}
          >
            {item.text}
          </Text>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject
  },
  text: {
    position: "absolute",
    maxWidth: "88%",
    color: "#fff",
    fontSize: 18,
    fontWeight: "700",
    textShadowColor: "rgba(0,0,0,0.74)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4
  }
});
