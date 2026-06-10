const fs = require("fs");

describe("startup diagnostics", () => {
  it("shows the resolved API base URL on the startup error screen", () => {
    const source = fs.readFileSync("App.tsx", "utf8");

    expect(source).toContain("API 地址");
    expect(source).toContain("{API_BASE_URL}");
  });
});
