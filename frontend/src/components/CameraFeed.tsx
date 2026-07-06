import { memo } from 'react';

interface CameraFeedProps {
  videoRef: React.Ref<HTMLVideoElement>;
}

/** Isolated video element — avoids re-renders when the rest of the viva page updates. */
export const CameraFeed = memo(function CameraFeed({ videoRef }: CameraFeedProps) {
  return (
    <div className="camera-frame">
      <video ref={videoRef} autoPlay playsInline muted />
    </div>
  );
});
