import type { ImageSourcePropType } from "react-native";

const SERIES_COVERS: Record<string, ImageSourcePropType> = {
  beipai_xunbao_biji: require("../../assets/covers/beipai_xunbao_biji.png"),
  beiwang: require("../../assets/covers/beiwang.webp"),
  huangnian_quancun_kenshupi: require("../../assets/covers/huangnian_quancun_kenshupi.webp"),
  jiali_jiawai: require("../../assets/covers/jiali_jiawai.jpg"),
  nanian_dongzhi: require("../../assets/covers/nanian_dongzhi.webp"),
  shibasui_tainainai: require("../../assets/covers/shibasui_tainainai.jpg"),
  siye: require("../../assets/covers/siye.webp"),
  tianxia_diyi_wanku: require("../../assets/covers/tianxia_diyi_wanku.webp"),
  xingde_xiangyu_lihunshi: require("../../assets/covers/xingde_xiangyu_lihunshi.jpg"),
  yunmiao_1: require("../../assets/covers/yunmiao_1.webp")
};

export function getSeriesCoverSource(seriesId: string | undefined): ImageSourcePropType | undefined {
  if (!seriesId) {
    return undefined;
  }
  return SERIES_COVERS[seriesId];
}
