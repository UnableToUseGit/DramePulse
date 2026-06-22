import Svg, { Path } from "react-native-svg";

export function BrokenHeartGlyph({ size = 24 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path
        d="M12 21s-1.1-.95-2.5-2.16C5.42 15.25 3 13.08 3 9.48 3 6.72 5.12 4.7 7.7 4.7c1.72 0 3.05.86 4.3 2.44 1.25-1.58 2.58-2.44 4.3-2.44 2.58 0 4.7 2.02 4.7 4.78 0 3.6-2.42 5.77-6.5 9.36C13.1 20.05 12 21 12 21Z"
        // fill="#f84f78" 
        fill="#b83a4b"
      />
      <Path d="M12.55 6.78 10.35 11l2.75-.22-1.7 5.9 4.18-7.42-2.7.24 1.28-2.72h-1.61Z" fill="#351018" />
    </Svg>
  );
}
