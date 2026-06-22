import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { ActionRailResonanceButton } from "../action-rail-resonance/ActionRailResonanceButton";
import { ActionRailResonanceSlot } from "../action-rail-resonance/ActionRailResonanceSlot";
import type { ResonanceTapState } from "../action-rail-resonance/tapState";
import type { ActionRailResonanceCue } from "../action-rail-resonance/types";
import { colors, playerOverlay } from "../theme";
import { LikeReactionButton } from "./LikeReactionButton";

export function PlayerActionRail({
  liked,
  onToggleLike,
  bottomOffset = 124,
  resonanceCue,
  resonanceTapState,
  onParticipateResonance
}: {
  liked: boolean;
  onToggleLike: () => void;
  bottomOffset?: number;
  resonanceCue?: ActionRailResonanceCue;
  resonanceTapState: ResonanceTapState;
  onParticipateResonance: (cue: ActionRailResonanceCue, nextState: ResonanceTapState) => void;
}) {
  return (
    <View style={[styles.root, { bottom: bottomOffset }]}>
      <ActionRailResonanceSlot cueId={resonanceCue?.cueId}>
        {resonanceCue ? (
          <ActionRailResonanceButton
            cue={resonanceCue}
            tapState={resonanceTapState}
            onParticipate={onParticipateResonance}
          />
        ) : null}
      </ActionRailResonanceSlot>
      <RailIcon icon="star" count="199.4万" />
      <RailIcon icon="chatbubble-ellipses" count="6626" accessibilityLabel="评论" />
      <LikeReactionButton count="30.8万" liked={liked} onToggle={onToggleLike} />
      <RailIcon icon="arrow-redo" count="5.3万" />
    </View>
  );
}

function RailIcon({
  icon,
  count,
  accessibilityLabel,
  onPress
}: {
  icon: keyof typeof Ionicons.glyphMap;
  count: string;
  accessibilityLabel?: string;
  onPress?: () => void;
}) {
  const content = (
    <>
      <View style={styles.iconWrap}>
        <Ionicons name={icon} size={35} color="#fff" />
      </View>
      <Text style={styles.text}>{count}</Text>
    </>
  );
  if (onPress) {
    return (
      <Pressable accessibilityRole="button" accessibilityLabel={accessibilityLabel} style={styles.item} onPress={onPress}>
        {content}
      </Pressable>
    );
  }
  return (
    <View style={styles.item}>
      {content}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    right: 8,
    alignItems: "center",
    gap: 15
  },
  item: {
    alignItems: "center",
    width: 56,
    gap: 1
  },
  iconWrap: {
    width: 48,
    height: 40,
    alignItems: "center",
    justifyContent: "center"
  },
  text: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "400",
    fontVariant: ["tabular-nums"],
  }
});
