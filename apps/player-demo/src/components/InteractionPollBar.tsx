import { Pressable, StyleSheet, Text, View } from "react-native";
import type { InteractionOption, InteractionPlan } from "../domain/types";
import { colors, radii, spacing } from "../theme";

function renderResultText(template: string | undefined, option: InteractionOption, ratio: number) {
  const fallback = "你和 {ratio}% 的观众一样选择了「{option}」";
  return (template || fallback).replace("{ratio}", String(ratio)).replace("{option}", option.text);
}

export function InteractionPollBar({
  plan,
  selectedOption,
  onSelect
}: {
  plan: InteractionPlan | undefined;
  selectedOption: InteractionOption | undefined;
  onSelect: (option: InteractionOption) => void;
}) {
  if (!plan) {
    return null;
  }
  const ratio = selectedOption ? 68 + (selectedOption.rank ?? 1) * 3 : 0;

  return (
    <View style={styles.root} pointerEvents="box-none">
      <View style={[styles.bar, selectedOption ? styles.resultBar : null]}>
        {selectedOption ? (
          <Text style={styles.resultText}>
            {renderResultText(plan?.feedback.resonance_text_template, selectedOption, Math.min(ratio, 86))}
          </Text>
        ) : (
          <>
            <Text style={styles.question}>{plan?.question ?? "高光互动测试"}</Text>
            <View style={styles.options}>
              {plan?.options.slice(0, 3).map((option) => (
                <Pressable key={option.option_id} style={styles.option} onPress={() => onSelect(option)}>
                  <Text style={styles.optionText}>{option.text}</Text>
                </Pressable>
              ))}
            </View>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    top: "42%",
    alignItems: "center"
  },
  bar: {
    maxWidth: "100%",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    backgroundColor: colors.panel,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.35,
    shadowRadius: 18
  },
  resultBar: {
    borderColor: "rgba(255,106,26,0.76)",
    backgroundColor: "rgba(28, 12, 5, 0.86)"
  },
  question: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "800",
    textAlign: "center"
  },
  options: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: spacing.sm,
    marginTop: spacing.sm
  },
  option: {
    paddingHorizontal: spacing.md,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: "rgba(255,255,255,0.13)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)"
  },
  optionText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800"
  },
  resultText: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "900"
  }
});
