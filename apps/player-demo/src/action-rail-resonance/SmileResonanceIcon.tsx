import Svg, { Path } from "react-native-svg";

const LAUGH_FACE_PATH =
  "M12 4.4a7.2 7.2 0 1 0 0 14.4 7.2 7.2 0 0 0 0-14.4ZM9.25 9.38a.92.92 0 1 0 0 1.84.92.92 0 0 0 0-1.84Zm5.5 0a.92.92 0 1 0 0 1.84.92.92 0 0 0 0-1.84ZM8.25 13.05C8.5 15.75 9.95 17.1 12 17.1C14.05 17.1 15.5 15.75 15.75 13.05Z";

export function SmileResonanceIcon({ isLit, size = 38 }: { isLit: boolean; size?: number }) {
  const faceColor = isLit ? "#ffcc4d" : "#ffffff";

  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d={LAUGH_FACE_PATH} fill={faceColor} fillRule="evenodd" />
    </Svg>
  );
}
