import { StyleSheet, Text, View } from "react-native";

export function DanmakuEntryButton() {
  return (
    <View pointerEvents="none" style={styles.root}>
      <Text style={styles.text}>弹</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    alignSelf: "flex-start",
    width: 34,
    height: 34,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 17,
    backgroundColor: "rgba(0,0,0,0.46)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.13)"
  },
  text: {
    color: "rgba(255,255,255,0.9)",
    fontSize: 17,
    fontWeight: "900",
    letterSpacing: 0
  }
});
