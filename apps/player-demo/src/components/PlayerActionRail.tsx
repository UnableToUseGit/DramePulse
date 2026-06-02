import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { ActionRailResonanceButton } from "../action-rail-resonance/ActionRailResonanceButton";
import { ActionRailResonanceSlot } from "../action-rail-resonance/ActionRailResonanceSlot";
import type { ResonanceTapState } from "../action-rail-resonance/tapState";
import type { ActionRailResonanceCue } from "../action-rail-resonance/types";
import { colors, spacing } from "../theme";
import { LikeReactionButton } from "./LikeReactionButton";

export function PlayerActionRail({
  liked,
  onToggleLike,
  onOpenStoryQa,
  resonanceCue,
  resonanceTapState,
  onParticipateResonance
}: {
  liked: boolean;
  onToggleLike: () => void;
  onOpenStoryQa: () => void;
  resonanceCue?: ActionRailResonanceCue;
  resonanceTapState: ResonanceTapState;
  onParticipateResonance: (cue: ActionRailResonanceCue, nextState: ResonanceTapState) => void;
}) {
  return (
    <View style={styles.root}>
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
      <RailIcon icon="chatbubble-ellipses" count="6626" accessibilityLabel="剧情问答" onPress={onOpenStoryQa} />
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
        <Ionicons name={icon} size={34} color="#fff" />
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
    right: 2,
    bottom: 124,
    alignItems: "center",
    gap: 24
  },
  item: {
    alignItems: "center",
    width: 58,
    gap: 0
  },
  iconWrap: {
    width: 54,
    height: 46,
    alignItems: "center",
    justifyContent: "center"
  },
  text: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "700",
    textShadowColor: "rgba(0,0,0,0.68)",
    textShadowRadius: 4
  }
});
