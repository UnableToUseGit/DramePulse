# Series Player 广告位 API

本文只记录 Series Player 中插入切片广告所需的最小接口。

## 请求

```http
GET /api/series/{series_id}/ad-slots
```

用途：

- 获取某个剧集播放队列中的广告插入位；
- 前端按 `after_episode_no` 把广告插到对应集后面；
- 第一版不做分页、频控、用户画像或复杂投放策略。

## 返回

```json
{
  "series_id": "beiwang",
  "slots": [
    {
      "slot_id": "beiwang_after_ep02_ad01",
      "after_episode_no": 2,
      "ad": {
        "ad_id": "ad_001",
        "video_url": "https://cdn.example.com/ads/ad_001.mp4",
        "duration": 12,
        "sponsor_label": "广告",
        "product_name": "云雾哑光口红",
        "product_description": "太奶奶同款短剧番外推荐：提气色、不张扬。",
        "character_name": "太奶奶",
        "cta_text": "查看同款",
        "price_text": "到手价 99 元",
        "selling_points": ["显气色", "哑光不拔干", "通勤约会都稳"]
      }
    }
  ]
}
```

## 字段说明

- `slot_id`：广告位 ID，前端用于生成稳定队列 key。
- `after_episode_no`：广告插在第几集后面。
- `ad_id`：广告素材 ID，后续可用于曝光、跳过和播完上报。
- `video_url`：广告视频地址。
- `duration`：广告时长，单位秒。
- `sponsor_label`：广告标识文案，例如“广告”。
- `product_name`：广告页主标题。
- `product_description`：广告页简介和商品说明。
- `character_name`：角色名，用于广告页标签。
- `cta_text`：广告页 CTA 按钮文案。
- `price_text`：商品价格文案。
- `selling_points`：商品卖点标签。
