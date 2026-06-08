from __future__ import annotations

from typing import Any


SUPPORTED_SOURCE_TYPES = {"plot", "performance", "character_appeal", "finale_judgment"}
SUPPORTED_INTERACTION_MODES = {"single_tap", "hold_burst", "repeat_tap", "stance_poll", "finale_rating"}
PLOT_PRIMARY_EXPRESSION_DEFINITIONS = (
    ("爽点", "主角或正义方在被压制、羞辱、质疑或不公平对待之后，当场反击、打脸、赢回主动权或惩罚恶人带来的解气爽感。"),
    ("甜点", "角色之间在暧昧、克制、误会、保护或双向在意的铺垫之后，关系出现明确升温、确认或亲密推进。"),
    ("泪点", "亲情、爱情、牺牲、重逢、告别、无私守护或善意在充分铺垫后兑现，带来感动、悲伤或泪目。"),
    ("笑点", "台词、动作、表演反应、误会、尴尬或前后反差形成明确笑点，观众自然想表达哈哈、笑死或绷不住。"),
)
LEGACY_PLOT_PRIMARY_EXPRESSION_ALIASES = {
    "爽到了": "爽点",
    "磕到了": "甜点",
    "看哭了": "泪点",
    "笑死": "笑点",
}
SUPPORTED_PLOT_PRIMARY_EXPRESSIONS = {
    label for label, _description in PLOT_PRIMARY_EXPRESSION_DEFINITIONS
} | set(LEGACY_PLOT_PRIMARY_EXPRESSION_ALIASES)

PERFORMANCE_KEYWORDS = ("笑死", "哈哈", "绷不住", "离谱", "抓马", "尬", "急了", "演技")
CHARACTER_APPEAL_KEYWORDS = ("好帅", "太帅", "太美", "漂亮", "老婆", "老公", "可爱", "眼神", "姐姐")
FINALE_KEYWORDS = ("大结局", "完结", "结局", "好剧", "烂尾", "没看够", "上头", "太短")


def _clean_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def normalize_plot_primary_expression(value: Any) -> str:
    expression = _clean_text(value)
    return LEGACY_PLOT_PRIMARY_EXPRESSION_ALIASES.get(expression, expression)


__all__ = [
    "CHARACTER_APPEAL_KEYWORDS",
    "FINALE_KEYWORDS",
    "LEGACY_PLOT_PRIMARY_EXPRESSION_ALIASES",
    "PERFORMANCE_KEYWORDS",
    "PLOT_PRIMARY_EXPRESSION_DEFINITIONS",
    "SUPPORTED_INTERACTION_MODES",
    "SUPPORTED_PLOT_PRIMARY_EXPRESSIONS",
    "SUPPORTED_SOURCE_TYPES",
    "normalize_plot_primary_expression",
]
