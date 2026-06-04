import Svg, { Path } from "react-native-svg";

const CRY_FACE_PATH =
  "M12 4.4a7.2 7.2 0 1 0 0 14.4 7.2 7.2 0 0 0 0-14.4ZM9.25 9.38a.92.92 0 1 0 0 1.84.92.92 0 0 0 0-1.84Zm5.5 0a.92.92 0 1 0 0 1.84.92.92 0 0 0 0-1.84Zm-5.88 6.12c.88-1.07 1.93-1.6 3.13-1.6s2.25.53 3.13 1.6l-1.22 1.01c-.55-.67-1.2-.99-1.91-.99s-1.36.32-1.91.99L8.87 15.5Z";

export function TearResonanceIcon({ isLit, size = 38 }: { isLit: boolean; size?: number }) {
  const faceColor = isLit ? "#ffcc4d" : "#ffffff";

  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d={CRY_FACE_PATH} fill={faceColor} fillRule="evenodd" />
      {isLit ? (
        <Path
          d="M6.9 11.7c1.08 1.38 1.64 2.36 1.64 3.2a1.78 1.78 0 0 1-1.78 1.86 1.73 1.73 0 0 1-1.74-1.8c0-.86.58-1.86 1.88-3.26Z"
          fill="#89c8ff"
        />
      ) : null}
    </Svg>
  );
}
