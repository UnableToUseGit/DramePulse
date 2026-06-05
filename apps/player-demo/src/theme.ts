export const colors = {
  black: "#050505",
  panel: "rgba(10, 10, 12, 0.74)",
  panelStrong: "rgba(0, 0, 0, 0.86)",
  scrim: "rgba(0, 0, 0, 0.34)",
  scrimStrong: "rgba(0, 0, 0, 0.58)",
  hairline: "rgba(255, 255, 255, 0.14)",
  text: "#FFFFFF",
  muted: "rgba(255, 255, 255, 0.68)",
  subdued: "rgba(255, 255, 255, 0.48)",
  faint: "rgba(255, 255, 255, 0.18)",
  accent: "#FF6A1A",
  accentDeep: "#E83A12",
  gold: "#FFD58A"
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24
};

export const radii = {
  pill: 999,
  panel: 18,
  small: 8
};

export const playerOverlay = {
  iconButtonSize: 42,
  topButtonHeight: 38,
  textShadow: {
    textShadowColor: "rgba(0, 0, 0, 0.66)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 5
  },
  softPanel: {
    backgroundColor: colors.scrim,
    borderWidth: 1,
    borderColor: colors.hairline
  },
  strongPanel: {
    backgroundColor: colors.scrimStrong,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.12)"
  }
};
