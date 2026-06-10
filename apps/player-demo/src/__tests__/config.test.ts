describe("config", () => {
  const originalValue = process.env.EXPO_PUBLIC_API_BASE_URL;
  const originalInteractionLabValue = process.env.EXPO_PUBLIC_ENABLE_INTERACTION_LAB;
  const originalPlaybackDebugValue = process.env.EXPO_PUBLIC_ENABLE_PLAYBACK_DEBUG_PANEL;
  const originalFastStartupValue = process.env.EXPO_PUBLIC_FAST_STARTUP;

  function loadConfig() {
    return require("../config") as typeof import("../config");
  }

  afterEach(() => {
    jest.resetModules();
    if (originalValue === undefined) {
      delete process.env.EXPO_PUBLIC_API_BASE_URL;
    } else {
      process.env.EXPO_PUBLIC_API_BASE_URL = originalValue;
    }
    if (originalInteractionLabValue === undefined) {
      delete process.env.EXPO_PUBLIC_ENABLE_INTERACTION_LAB;
    } else {
      process.env.EXPO_PUBLIC_ENABLE_INTERACTION_LAB = originalInteractionLabValue;
    }
    if (originalPlaybackDebugValue === undefined) {
      delete process.env.EXPO_PUBLIC_ENABLE_PLAYBACK_DEBUG_PANEL;
    } else {
      process.env.EXPO_PUBLIC_ENABLE_PLAYBACK_DEBUG_PANEL = originalPlaybackDebugValue;
    }
    if (originalFastStartupValue === undefined) {
      delete process.env.EXPO_PUBLIC_FAST_STARTUP;
    } else {
      process.env.EXPO_PUBLIC_FAST_STARTUP = originalFastStartupValue;
    }
  });

  it("defaults to the local iOS API base URL", () => {
    delete process.env.EXPO_PUBLIC_API_BASE_URL;

    const config = loadConfig();

    expect(config.API_BASE_URL).toBe("http://127.0.0.1:8000");
  });

  it("allows the API base URL to be overridden by environment", () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";

    const config = loadConfig();

    expect(config.API_BASE_URL).toBe("http://127.0.0.1:8000");
  });

  it("keeps the interaction lab hidden unless explicitly enabled", () => {
    delete process.env.EXPO_PUBLIC_ENABLE_INTERACTION_LAB;

    expect(loadConfig().ENABLE_INTERACTION_LAB).toBe(false);

    jest.resetModules();
    process.env.EXPO_PUBLIC_ENABLE_INTERACTION_LAB = "true";

    expect(loadConfig().ENABLE_INTERACTION_LAB).toBe(true);
  });

  it("keeps the playback debug panel hidden unless explicitly enabled", () => {
    delete process.env.EXPO_PUBLIC_ENABLE_PLAYBACK_DEBUG_PANEL;

    expect(loadConfig().ENABLE_PLAYBACK_DEBUG_PANEL).toBe(false);

    jest.resetModules();
    process.env.EXPO_PUBLIC_ENABLE_PLAYBACK_DEBUG_PANEL = "true";

    expect(loadConfig().ENABLE_PLAYBACK_DEBUG_PANEL).toBe(true);
  });

  it("keeps fast startup disabled unless explicitly enabled", () => {
    delete process.env.EXPO_PUBLIC_FAST_STARTUP;

    expect(loadConfig().ENABLE_FAST_STARTUP).toBe(false);

    jest.resetModules();
    process.env.EXPO_PUBLIC_FAST_STARTUP = "true";

    expect(loadConfig().ENABLE_FAST_STARTUP).toBe(true);
  });
});
