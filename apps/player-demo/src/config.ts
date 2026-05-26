declare const process: {
  env?: {
    EXPO_PUBLIC_API_BASE_URL?: string;
  };
};

export const API_BASE_URL = process.env?.EXPO_PUBLIC_API_BASE_URL?.trim() || "/";
export const ENABLE_INTERACTION_LAB = true;
