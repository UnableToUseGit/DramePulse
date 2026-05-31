import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

const TABS = ["首页", "剧场", "商城", "福利", "我的"];

export function PlayerBottomTabs({ onOpenTheater }: { onOpenTheater: () => void }) {
  return (
    <View style={styles.root}>
      {TABS.map((item, index) => {
        const isTheater = item === "剧场";
        return (
          <Pressable
            key={item}
            accessibilityRole={isTheater ? "button" : undefined}
            accessibilityLabel={isTheater ? "打开剧场" : undefined}
            disabled={!isTheater}
            style={styles.tab}
            onPress={isTheater ? onOpenTheater : undefined}
          >
            <Text style={[styles.text, index === 0 ? styles.active : null]}>{item}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 74,
    paddingHorizontal: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "rgba(18,18,18,0.94)"
  },
  text: {
    color: "rgba(255,255,255,0.52)",
    fontSize: 20,
    fontWeight: "900"
  },
  tab: {
    minWidth: 48,
    minHeight: 46,
    alignItems: "center",
    justifyContent: "center"
  },
  active: {
    color: colors.text
  }
});
