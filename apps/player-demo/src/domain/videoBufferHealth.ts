const DEFAULT_REPORT_INTERVAL_SEC = 2;
const DEFAULT_LOW_BUFFER_THRESHOLD_SEC = 1.5;

function roundToMillis(value: number) {
  return Math.round(value * 1000) / 1000;
}

export function getVideoBufferHealthSample({
  bufferedPosition,
  currentTime,
  isPlaying,
  lastReportedTime,
  lowBufferThresholdSec = DEFAULT_LOW_BUFFER_THRESHOLD_SEC,
  reportIntervalSec = DEFAULT_REPORT_INTERVAL_SEC,
  shouldPlay
}: {
  bufferedPosition: number | undefined;
  currentTime: number | undefined;
  isPlaying: boolean;
  lastReportedTime: number | undefined;
  lowBufferThresholdSec?: number;
  reportIntervalSec?: number;
  shouldPlay: boolean;
}) {
  if (!shouldPlay || !isPlaying || currentTime === undefined || bufferedPosition === undefined) {
    return {
      nextLastReportedTime: lastReportedTime,
      shouldRecord: false
    };
  }
  if (!Number.isFinite(currentTime) || !Number.isFinite(bufferedPosition) || bufferedPosition < 0) {
    return {
      nextLastReportedTime: lastReportedTime,
      shouldRecord: false
    };
  }

  const bufferAhead = Math.max(0, bufferedPosition - currentTime);
  const isLowBuffer = bufferAhead <= lowBufferThresholdSec;
  const elapsedSinceLastReport = lastReportedTime === undefined ? Infinity : currentTime - lastReportedTime;
  if (!isLowBuffer && elapsedSinceLastReport < reportIntervalSec) {
    return {
      nextLastReportedTime: lastReportedTime,
      shouldRecord: false
    };
  }

  return {
    details: {
      bufferAhead: roundToMillis(bufferAhead),
      bufferedPosition: roundToMillis(bufferedPosition),
      currentTime: roundToMillis(currentTime),
      isLowBuffer
    },
    nextLastReportedTime: currentTime,
    shouldRecord: true
  };
}
