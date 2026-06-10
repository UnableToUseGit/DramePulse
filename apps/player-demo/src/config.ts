import { NativeModules, Platform } from "react-native";

const API_PORT = "8000";

declare const process: {
  env?: {
    EXPO_PUBLIC_API_BASE_URL?: string;
    EXPO_PUBLIC_API_REQUEST_TIMEOUT_MS?: string;
    EXPO_PUBLIC_ENABLE_INTERACTION_LAB?: string;
    EXPO_PUBLIC_ENABLE_PLAYBACK_DEBUG_PANEL?: string;
    EXPO_PUBLIC_FAST_STARTUP?: string;
  };
};

function getDevServerHost() {
  const sourceCode = NativeModules.SourceCode as { scriptURL?: string } | undefined;
  const scriptUrl = sourceCode?.scriptURL;
  const match = scriptUrl?.match(/^https?:\/\/([^/:]+)/);
  return match?.[1];
}

function getDefaultApiBaseUrl() {
  const devServerHost = getDevServerHost();
  if (devServerHost && devServerHost !== "localhost" && devServerHost !== "127.0.0.1") {
    return `http://${devServerHost}:${API_PORT}`;
  }

  if (Platform.OS === "web") {
    return "/";
  }

  if (Platform.OS === "android") {
    return `http://10.0.2.2:${API_PORT}`;
  }

  return `http://127.0.0.1:${API_PORT}`;
}

function getRequestTimeoutMs() {
  const timeoutMs = Number(process.env?.EXPO_PUBLIC_API_REQUEST_TIMEOUT_MS);
  return Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : 8000;
}

export const API_BASE_URL = process.env?.EXPO_PUBLIC_API_BASE_URL?.trim() || getDefaultApiBaseUrl();
export const API_REQUEST_TIMEOUT_MS = getRequestTimeoutMs();
export const ENABLE_INTERACTION_LAB = process.env?.EXPO_PUBLIC_ENABLE_INTERACTION_LAB === "true";
export const ENABLE_PLAYBACK_DEBUG_PANEL = process.env?.EXPO_PUBLIC_ENABLE_PLAYBACK_DEBUG_PANEL === "true";
export const ENABLE_FAST_STARTUP = process.env?.EXPO_PUBLIC_FAST_STARTUP === "true";
