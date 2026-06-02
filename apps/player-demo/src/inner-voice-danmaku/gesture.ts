const SEND_DISTANCE_PX = 28;
const RESPONDER_VERTICAL_DISTANCE_PX = 6;
const BASE_LAUNCH_Y_PX = 180;
const MAX_EXTRA_LAUNCH_Y_PX = 64;

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
