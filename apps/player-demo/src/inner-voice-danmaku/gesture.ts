const SEND_DISTANCE_PX = 28;
const RESPONDER_VERTICAL_DISTANCE_PX = 6;
const BASE_LAUNCH_Y_PX = 180;
const MAX_EXTRA_LAUNCH_Y_PX = 64;
const PAN_RESPONDER_VELOCITY_SCALE = 1000;
const MIN_UPWARD_FLING_VELOCITY = 1050;
const UPWARD_RELEASE_BOOST = 520;
const MAX_HORIZONTAL_FLING_VELOCITY = 1400;

export function shouldClaimInnerVoiceDrag({ dx, dy }: { dx: number; dy: number }) {
  return dy < -RESPONDER_VERTICAL_DISTANCE_PX && Math.abs(dy) > Math.abs(dx);
}

export function shouldSendInnerVoiceDraft({ dx, dy }: { dx: number; dy: number }) {
  const upwardDistance = Math.max(0, -dy);
  const diagonalDistance = Math.sqrt(Math.max(0, dx) ** 2 + upwardDistance ** 2);
  return upwardDistance >= SEND_DISTANCE_PX || (dx > 0 && upwardDistance >= 14 && diagonalDistance >= SEND_DISTANCE_PX);
}

export function getInnerVoiceDragState({ dx, dy }: { dx: number; dy: number }) {
  const upwardDistance = Math.max(0, -dy);
  const diagonalDistance = Math.sqrt(Math.max(0, dx) ** 2 + upwardDistance ** 2);
  const progress = Math.min(1, Math.max(upwardDistance, diagonalDistance) / SEND_DISTANCE_PX);

  return {
    translateX: dx,
    translateY: dy,
    progress
  };
}

export function getInnerVoiceLaunchTarget({ dx, dy, vy }: { dx: number; dy: number; vy: number }) {
  const upwardVelocity = Math.max(0, -vy);
  const extraLaunchY = Math.min(MAX_EXTRA_LAUNCH_Y_PX, Math.round(upwardVelocity * 40));
  return {
    translateX: Math.max(-18, Math.min(42, dx)) + 12,
    translateY: -(BASE_LAUNCH_Y_PX + Math.min(40, Math.max(0, -dy - SEND_DISTANCE_PX)) + extraLaunchY)
  };
}

export function getInnerVoiceFlingVelocity({ vx, vy }: { vx: number; vy: number }) {
  const velocityX = Math.max(
    -MAX_HORIZONTAL_FLING_VELOCITY,
    Math.min(MAX_HORIZONTAL_FLING_VELOCITY, vx * PAN_RESPONDER_VELOCITY_SCALE)
  );
  const velocityY = Math.min(
    -MIN_UPWARD_FLING_VELOCITY,
    vy * PAN_RESPONDER_VELOCITY_SCALE - UPWARD_RELEASE_BOOST
  );

  return { velocityX, velocityY };
}
