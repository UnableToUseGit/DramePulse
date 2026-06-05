export type RoleCommerceAdPlacement = "after_first_video" | "after_video";

export interface RoleCommerceFeedAd {
  adId: string;
  campaignId: string;
  placement: RoleCommerceAdPlacement;
  afterVideoId?: string;
  sponsorLabel: string;
  characterName: string;
  productName: string;
  title: string;
  hook: string;
  productDescription: string;
  voiceoverLines: string[];
  sellingPoints: string[];
  priceText: string;
  ctaText: string;
}

export const DEMO_ROLE_COMMERCE_ADS: RoleCommerceFeedAd[] = [
  {
    adId: "rc_case1_grandma_lipstick",
    campaignId: "case1_grandma_lipstick_001",
    placement: "after_first_video",
    sponsorLabel: "广告",
    characterName: "太奶奶",
    productName: "云雾哑光口红",
    title: "太奶奶亲自挑的气色口红",
    hook: "别让气色输在第一眼。",
    productDescription: "太奶奶同款短剧番外推荐：提气色、不张扬，适合上班见人、出门办事前快速补状态。",
    voiceoverLines: ["这支颜色，提气色，不张扬。", "上班见人、出门办事，抹一下就有精神。", "别怕踩雷，这事我来定。"],
    sellingPoints: ["显气色", "哑光不拔干", "通勤约会都稳"],
    priceText: "到手价 99 元",
    ctaText: "查看同款"
  }
];
