import Svg, { Path } from "react-native-svg";

const SMILE_FACE_PATH =
  "M12 4.4a7.2 7.2 0 1 0 0 14.4 7.2 7.2 0 0 0 0-14.4ZM9.25 9.38a.92.92 0 1 0 0 1.84.92.92 0 0 0 0-1.84Zm5.5 0a.92.92 0 1 0 0 1.84.92.92 0 0 0 0-1.84ZM8.7 13.7c.76 1.34 1.9 2.01 3.3 2.01s2.54-.67 3.3-2.01l1.34.76c-1.02 1.8-2.58 2.7-4.64 2.7s-3.62-.9-4.64-2.7L8.7 13.7Z";

export function SmileResonanceIcon({ isLit, size = 38 }: { isLit: boolean; size?: number }) {
  const faceColor = isLit ? "#ffcc4d" : "#ffffff";

  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d={SMILE_FACE_PATH} fill={faceColor} fillRule="evenodd" />
    </Svg>
  );
}
