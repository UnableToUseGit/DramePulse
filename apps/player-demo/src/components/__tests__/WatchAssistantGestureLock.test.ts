declare const require: (path: string) => any;

describe("Watch assistant gesture lock", () => {
  it("locks feed scrolling while the panel is rendered and merges that lock with other player gestures", () => {
    const fs = require("fs");
    const playerFeedSource = fs.readFileSync("src/components/PlayerFeed.tsx", "utf8");
    const panelSource = fs.readFileSync("src/components/WatchAssistantPanel.tsx", "utf8");

    expect(playerFeedSource).toContain("const [isAssistantInteractionBlocked, setIsAssistantInteractionBlocked] = useState(false);");
    expect(playerFeedSource).toContain("isTimelineDragging || isAssistantInteractionBlocked");
    expect(playerFeedSource).toContain("onInteractionBlockChange={setIsAssistantInteractionBlocked}");

    expect(panelSource).toContain("onInteractionBlockChange?: (isBlocked: boolean) => void;");
    expect(panelSource).toContain("onInteractionBlockChange?.(shouldRender);");
  });
});
