import Svg, { Ellipse, Path } from "react-native-svg";

export function CandyResonanceIcon({ isLit }: { isLit: boolean }) {
  const colors = isLit
    ? {
        body: "#ff7bbd",
        wrapper: "#ffd66e",
        detail: "#fff1bd"
      }
    : {
        body: "#ffffff",
        wrapper: "#ffffff",
        detail: "#ffffff"
      };

  return (
    <Svg width={38} height={38} viewBox="0 0 1024 1024">
      <Path
        d="M314 410c-64 64-64 168 0 232l62 62c64 64 168 64 232 0l102-102c64-64 64-168 0-232l-62-62c-64-64-168-64-232 0L314 410z"
        fill={colors.body}
      />
      <Path
        d="M642 314l72-204c8-24 38-32 56-14l158 158c18 18 10 48-14 56l-204 72c-15 5-32 1-44-11l-13-13c-12-12-16-29-11-44z"
        fill={colors.wrapper}
      />
      <Path
        d="M382 710l-72 204c-8 24-38 32-56 14L96 770c-18-18-10-48 14-56l204-72c15-5 32-1 44 11l13 13c12 12 16 29 11 44z"
        fill={colors.wrapper}
      />
      <Path
        d="M594 392l126-34c16-4 32 6 36 22s-6 32-22 36l-126 34c-16 4-32-6-36-22s6-32 22-36z"
        fill={colors.detail}
      />
      <Path
        d="M292 632l-126 34c-16 4-32-6-36-22s6-32 22-36l126-34c16-4 32 6 36 22s-6 32-22 36z"
        fill={colors.detail}
      />
      <Ellipse cx={512} cy={506} rx={106} ry={78} fill={colors.detail} opacity={isLit ? 0.24 : 0.18} />
    </Svg>
  );
}
