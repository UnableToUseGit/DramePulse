import Svg, { Text as SvgText } from "react-native-svg";

export function ThrillWordGlyph({ isLit = true, size = 42 }: { isLit?: boolean; size?: number }) {
  const fill = isLit ? "#ff6a1a" : "#ffffff";

  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <SvgText
        x="12"
        y="16.5"
        fill={fill}
        fontFamily="PingFang SC"
        fontSize="15.6"
        fontWeight="900"
        textAnchor="middle"
      >
        爽
      </SvgText>
    </Svg>
  );
}
