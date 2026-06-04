import { ThrillWordGlyph } from "./ThrillWordGlyph";

export function ThrillResonanceIcon({ isLit, size = 42 }: { isLit: boolean; size?: number }) {
  return <ThrillWordGlyph isLit={isLit} size={size} />;
}
