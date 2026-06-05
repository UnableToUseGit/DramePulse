import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, playerOverlay, spacing } from "../theme";

const TABS = ["首页", "剧场", "商城", "福利", "我的"];

export function PlayerBottomTabs({
  activeTab = "首页",
  onPressHome,
  onPressTheater
}: {
  activeTab?: string;
  onPressHome?: () => void;
  onPressTheater?: () => void;
}) {
  return (
    <View style={styles.root}>
      {TABS.map((item) => {
        const isActive = item === activeTab;
        const isHome = item === "首页";
        const isTheater = item === "剧场";
        const handler = isHome ? onPressHome : isTheater ? onPressTheater : undefined;
        return (
          <Pressable
            key={item}
            accessibilityRole={handler ? "button" : undefined}
            disabled={!handler}
            hitSlop={10}
            onPress={handler}
          >
            <Text style={[styles.text, isActive ? styles.active : null]}>{item}</Text>
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
    height: 70,
    paddingHorizontal: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "rgba(10,10,10,0.9)",
    borderTopWidth: 1,
    borderTopColor: "rgba(255,255,255,0.08)"
  },
  text: {
    color: "rgba(255,255,255,0.46)",
    fontSize: 19,
    fontWeight: "900",
    ...playerOverlay.textShadow
  },
  active: {
    color: colors.text
  }
});
