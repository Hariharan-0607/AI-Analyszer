import { memo } from 'react';
import { CameraFeed } from './CameraFeed';

interface CameraPanelProps {
  videoRef: React.Ref<HTMLVideoElement>;
  cameraOn: boolean;
  modelReady: boolean;
  identityStatus: 'pending' | 'verified' | 'failed';
  monitoring: boolean;
}

export const CameraPanel = memo(function CameraPanel({
  videoRef,
  cameraOn,
  modelReady,
  identityStatus,
  monitoring,
}: CameraPanelProps) {
  return (
    <div className="card camera-card">
      <h3>Camera Monitor</h3>
      <CameraFeed videoRef={videoRef} />
      <div className="status-bar">
        <span className={`badge ${cameraOn ? 'ok' : 'err'}`}>
          Camera {cameraOn ? 'ON' : 'OFF'}
        </span>
        <span className={`badge ${modelReady ? 'ok' : 'warn'}`}>
          Face Model {modelReady ? 'Ready' : 'Loading'}
        </span>
        <span
          className={`badge ${
            identityStatus === 'verified' ? 'ok' : identityStatus === 'failed' ? 'err' : 'warn'
          }`}
        >
          Identity {identityStatus}
        </span>
        <span className={`badge ${monitoring ? 'ok' : 'warn'}`}>
          Monitoring {monitoring ? 'Active' : 'Inactive'}
        </span>
      </div>
      <p className="camera-note">
        Video stays on your device. Only integrity events are sent to the server.
      </p>
    </div>
  );
});
