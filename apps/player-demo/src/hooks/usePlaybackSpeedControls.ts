import { useCallback, useEffect, useRef, useState } from "react";
import type { PlaybackRate } from "../components/SpeedSelector";

export function usePlaybackSpeedControls({
  isActive,
  isStarted,
  onStart,
  resetKey,
  onTap
}: {
  isActive: boolean;
  isStarted: boolean;
  onStart: () => void;
  resetKey: string;
  onTap: () => void;
}) {
  const [playbackRate, setPlaybackRate] = useState<PlaybackRate>(1);
  const [isSpeedMenuOpen, setIsSpeedMenuOpen] = useState(false);
  const [isHoldingFastForward, setIsHoldingFastForward] = useState(false);
  const didLongPressSpeedRef = useRef(false);
  const effectivePlaybackRate = isHoldingFastForward ? 2 : playbackRate;

  useEffect(() => {
    setPlaybackRate(1);
    setIsSpeedMenuOpen(false);
    setIsHoldingFastForward(false);
    didLongPressSpeedRef.current = false;
  }, [resetKey]);

  useEffect(() => {
    if (!isActive) {
      setIsHoldingFastForward(false);
      setIsSpeedMenuOpen(false);
      didLongPressSpeedRef.current = false;
    }
  }, [isActive]);

  const toggleSpeedMenu = useCallback(() => {
    setIsSpeedMenuOpen((open) => !open);
  }, []);

  const selectPlaybackRate = useCallback((rate: PlaybackRate) => {
    setPlaybackRate(rate);
    setIsSpeedMenuOpen(false);
  }, []);

  const handleRightPress = useCallback(() => {
    if (didLongPressSpeedRef.current) {
      didLongPressSpeedRef.current = false;
      return;
    }
    onTap();
  }, [onTap]);

  const handleRightLongPress = useCallback(() => {
    if (!isActive) {
      return;
    }
    didLongPressSpeedRef.current = true;
    if (!isStarted) {
      onStart();
    }
    setIsHoldingFastForward(true);
  }, [isActive, isStarted, onStart]);

  const handleRightPressOut = useCallback(() => {
    setIsHoldingFastForward(false);
  }, []);

  return {
    effectivePlaybackRate,
    handleRightLongPress,
    handleRightPress,
    handleRightPressOut,
    isHoldingFastForward,
    isSpeedMenuOpen,
    playbackRate,
    selectPlaybackRate,
    toggleSpeedMenu
  };
}
