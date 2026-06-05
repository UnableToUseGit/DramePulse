import Svg, { Text as SvgText } from "react-native-svg";

export function ThrillWordGlyph({ isLit = true, size = 42 }: { isLit?: boolean; size?: number }) {
  const fill = isLit ? "#ffd166" : "#ffffff";
  const stroke = isLit ? "#b93408" : "rgba(0,0,0,0.42)";

  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <SvgText
        x="12"
        y="16.5"
        fill={fill}
        stroke={stroke}
        strokeWidth={0.72}
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
