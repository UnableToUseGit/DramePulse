import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

const TABS = ["首页", "剧场", "商城", "福利", "我的"];

export function PlayerBottomTabs() {
  return (
    <View style={styles.root}>
      {TABS.map((item, index) => (
        <Text key={item} style={[styles.text, index === 0 ? styles.active : null]}>
          {item}
        </Text>
      ))}
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
  active: {
    color: colors.text
  }
});
