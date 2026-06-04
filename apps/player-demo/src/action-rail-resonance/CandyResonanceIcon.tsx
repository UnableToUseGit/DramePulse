import Svg, { Path } from "react-native-svg";

const CANDY_WRAPPER_PATH =
  "M6.31,15l-2.5.6a1,1,0,0,0-.75,1.24,1,1,0,0,0,.27.48l3,3a1,1,0,0,0,1.44,0A1,1,0,0,0,8,19.79l.61-2.5ZM17.63,8.27l2.49-.61A1,1,0,0,0,20.6,6L17.66,3a1,1,0,0,0-1.45,0,1.09,1.09,0,0,0-.27.48L15.34,6l2.29,2.29Z";

const CANDY_BODY_PATH =
  "M9.31,7.93,7,10.28l8,4.63,2.34-2.35-8-4.63Zm8.93,3.58a2.55,2.55,0,0,0-.42-3L15.11,5.75a2.55,2.55,0,0,0-3.61,0h0L10.31,6.94ZM6.08,14.78a2.56,2.56,0,0,1-.1-3.5l8,4.62L12.4,17.49a2.57,2.57,0,0,1-3.61,0h0Z";

export function CandyResonanceIcon({ isLit, size = 38 }: { isLit: boolean; size?: number }) {
  const fills = isLit
    ? {
        wrapper: "#ff91b0",
        body: "#f71762"
      }
    : {
        wrapper: "#ffffff",
        body: "#ffffff"
      };

  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d={CANDY_WRAPPER_PATH} fill={fills.wrapper} />
      <Path d={CANDY_BODY_PATH} fill={fills.body} />
    </Svg>
  );
}
