import { getSeriesCoverSource } from "../seriesCovers";

describe("seriesCovers", () => {
  it("resolves bundled cover assets for every imported series id", () => {
    const seriesIds = [
      "beipai_xunbao_biji",
      "beiwang",
      "huangnian_quancun_kenshupi",
      "jiali_jiawai",
      "nanian_dongzhi",
      "shibasui_tainainai",
      "siye",
      "tianxia_diyi_wanku",
      "xingde_xiangyu_lihunshi",
      "yunmiao_1"
    ];

    expect(seriesIds.every((seriesId) => getSeriesCoverSource(seriesId) !== undefined)).toBe(true);
  });

  it("resolves bundled cover assets for cloud series ids", () => {
    const cloudSeriesIds = [
      "beiwang",
      "jialijiawai",
      "naniandonzhi",
      "shibasui_tainainai",
      "tianxiadiyiwanku",
      "yunmiao1"
    ];

    expect(cloudSeriesIds.every((seriesId) => getSeriesCoverSource(seriesId) !== undefined)).toBe(true);
  });

  it("returns undefined for unknown series id", () => {
    expect(getSeriesCoverSource("unknown_series")).toBeUndefined();
    expect(getSeriesCoverSource(undefined)).toBeUndefined();
  });
});
