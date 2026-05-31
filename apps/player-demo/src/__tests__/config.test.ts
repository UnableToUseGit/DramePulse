describe("config", () => {
  const originalValue = process.env.EXPO_PUBLIC_API_BASE_URL;

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
});
