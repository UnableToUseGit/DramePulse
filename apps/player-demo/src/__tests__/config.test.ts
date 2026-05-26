describe("config", () => {
  const originalValue = process.env.EXPO_PUBLIC_API_BASE_URL;

  afterEach(() => {
    jest.resetModules();
    if (originalValue === undefined) {
      delete process.env.EXPO_PUBLIC_API_BASE_URL;
    } else {
      process.env.EXPO_PUBLIC_API_BASE_URL = originalValue;
    }
  });

  it("defaults to the same-origin API base URL", async () => {
    delete process.env.EXPO_PUBLIC_API_BASE_URL;

    const config = await import("../config");

    expect(config.API_BASE_URL).toBe("/");
  });

  it("allows the API base URL to be overridden by environment", async () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";

    const config = await import("../config");

    expect(config.API_BASE_URL).toBe("http://127.0.0.1:8000");
  });
});
