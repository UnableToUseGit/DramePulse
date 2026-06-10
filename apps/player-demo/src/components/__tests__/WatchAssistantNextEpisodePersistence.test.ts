declare const require: (path: string) => any;

describe("Watch assistant feed overlay", () => {
  it("keeps the assistant panel at feed level instead of carrying it through video pages", () => {
    const fs = require("fs");
    const playerPageSource = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");
    const playerFeedSource = fs.readFileSync("src/components/PlayerFeed.tsx", "utf8");

    expect(playerPageSource).not.toContain("<WatchAssistantPanel");
    expect(playerPageSource).not.toContain("incomingAssistantCarryState");
    expect(playerPageSource).toContain("assistantActionRequest?: WatchAssistantActionRequest;");
    expect(playerPageSource).toContain("onAssistantActionApplied?:");

    expect(playerFeedSource).toContain("WatchAssistantPanel");
    expect(playerFeedSource).toContain("assistantActionRequest");
    expect(playerFeedSource).toContain("onAssistantActionApplied={handleAssistantActionApplied}");
    expect(playerFeedSource).toContain("onInteractionBlockChange={setIsAssistantInteractionBlocked}");
  });
});
