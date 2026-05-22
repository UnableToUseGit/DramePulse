import { StyleSheet, Text, View } from "react-native";
import type { InteractionOption } from "../domain/types";
import { colors } from "../theme";

export function FeedbackBurst({ selectedOption }: { selectedOption: InteractionOption | undefined }) {
  if (!selectedOption) {
    return null;
  }
  const items = [selectedOption.danmaku_text, "这波懂了！", "我也这么选"];

  return (
    <View pointerEvents="none" style={styles.root}>
      {items.map((text, index) => (
        <Text key={`${text}-${index}`} style={[styles.text, { top: 250 + index * 36, right: 16 + index * 30 }]}>
          {text}
        </Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject
  },
  text: {
    position: "absolute",
    color: colors.gold,
    fontSize: 17,
    fontWeight: "900",
    textShadowColor: colors.accentDeep,
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 8
  }
});
