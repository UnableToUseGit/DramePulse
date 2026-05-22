import { ScrollView, StyleSheet, Text, View } from "react-native";
import type { InteractionPlan, InteractionStats, UserEvent } from "../domain/types";
import { colors, radii, spacing } from "../theme";

export function DebugPanel({
  visible,
  currentTime,
  activePlan,
  events,
  stats
}: {
  visible: boolean;
  currentTime: number;
  activePlan: InteractionPlan | undefined;
  events: UserEvent[];
  stats: InteractionStats;
}) {
  if (!visible) {
    return null;
  }

  return (
    <View style={styles.root}>
      <Text style={styles.title}>DramePulse Debug</Text>
      <Text style={styles.line}>time: {currentTime.toFixed(2)}s</Text>
      <Text style={styles.line}>highlight: {activePlan?.highlight_id ?? "none"}</Text>
      <Text style={styles.line}>interaction: {activePlan?.interaction_id ?? "none"}</Text>
      <Text style={styles.line}>
        stats: exp {stats.exposure_count} / click {stats.click_count} / feedback {stats.feedback_shown_count} /
        dismiss {stats.dismiss_count}
      </Text>
      <ScrollView style={styles.events}>
        {events.slice(-8).map((event, index) => (
          <Text key={`${event.timestamp}-${index}`} style={styles.event}>
            {event.event_type} · {event.client_time.toFixed(1)}s {event.option_id ? `· ${event.option_id}` : ""}
          </Text>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    top: 90,
    left: spacing.md,
    right: spacing.md,
    maxHeight: 260,
    padding: spacing.md,
    borderRadius: radii.panel,
    backgroundColor: colors.panelStrong,
    borderWidth: 1,
    borderColor: "rgba(255,106,26,0.5)"
  },
  title: {
    color: colors.accent,
    fontSize: 15,
    fontWeight: "900",
    marginBottom: spacing.xs
  },
  line: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "700",
    marginTop: 2
  },
  events: {
    marginTop: spacing.sm
  },
  event: {
    color: colors.muted,
    fontSize: 11,
    marginBottom: 3
  }
});
