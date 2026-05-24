import { EmojiHoldExample } from "./EmojiHoldExample";
import { PollBarExample } from "./PollBarExample";
import type { InteractionExample, InteractionPresentationType } from "./types";

export function InteractionExampleRenderer({
  example,
  presentationType,
  visible,
  onDismiss
}: {
  example: InteractionExample;
  presentationType: InteractionPresentationType;
  visible: boolean;
  onDismiss: () => void;
}) {
  if (!visible || presentationType === "none") {
    return null;
  }

  if (presentationType === "poll_bar") {
    return <PollBarExample example={example} onDismiss={onDismiss} />;
  }

  return <EmojiHoldExample example={example} onDismiss={onDismiss} />;
}
