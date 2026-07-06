import { useEffect } from 'react';

export interface IntegrityNotification {
  id: string;
  type: string;
  message: string;
  time: string;
}

const FLAG_MESSAGES: Record<string, string> = {
  interview_started: 'Viva monitoring is now active.',
  id_verified: 'Identity verified successfully.',
  id_failed: 'Identity verification failed.',
  gaze_off_screen: 'Strike: You looked away from the screen.',
  camera_changed: 'Strike: Webcam source changed during the exam.',
  camera_disconnected: 'Strike: Webcam disconnected or interrupted.',
  secondary_device_detected: 'Strike: Phone or secondary device detected in view.',
  multiple_faces_detected: 'Strike: More than one person detected on camera.',
  face_not_detected: 'Your face is not visible to the camera.',
  tab_switched: 'Tab switch detected — remain on this page.',
  fullscreen_exited: 'Strike: Fullscreen exited — return to fullscreen to continue.',
  paste_attempted: 'Strike: Paste attempt blocked and recorded.',
  screenshot_detected: 'Strike: Screenshot capture detected.',
  connection_lost: 'Monitoring connection interrupted.',
  snapshot_captured: 'Monitoring heartbeat — session active.',
};

export function messageForFlag(type: string): string {
  return FLAG_MESSAGES[type] ?? `Integrity flag: ${type.replace(/_/g, ' ')}`;
}

interface Props {
  notifications: IntegrityNotification[];
  onDismiss: (id: string) => void;
  onDismissAll: () => void;
}

function ToastItem({
  notification,
  onDismiss,
}: {
  notification: IntegrityNotification;
  onDismiss: (id: string) => void;
}) {
  const isInfo =
    notification.type.includes('snapshot') || notification.type === 'interview_started';
  const isStrike =
    notification.type === 'screenshot_detected' ||
    notification.type === 'paste_attempted' ||
    notification.type === 'fullscreen_exited' ||
    notification.type === 'gaze_off_screen' ||
    notification.type === 'camera_changed' ||
    notification.type === 'camera_disconnected' ||
    notification.type === 'secondary_device_detected' ||
    notification.type === 'multiple_faces_detected';

  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(notification.id), isInfo ? 4000 : 8000);
    return () => window.clearTimeout(timer);
  }, [notification.id, isInfo, onDismiss]);

  return (
    <div className={`integrity-toast ${isStrike ? 'strike' : isInfo ? 'info' : 'warn'}`}>
      <div className="integrity-toast-body">
        <strong>{notification.time}</strong>
        <span>{notification.message}</span>
      </div>
      <button
        type="button"
        className="integrity-toast-close"
        aria-label="Dismiss alert"
        onClick={() => onDismiss(notification.id)}
      >
        ×
      </button>
    </div>
  );
}

export function IntegrityNotifications({ notifications, onDismiss, onDismissAll }: Props) {
  if (notifications.length === 0) return null;

  const visible = notifications.slice(-3).reverse();

  return (
    <div className="integrity-toast-container" aria-live="polite" aria-relevant="additions">
      <div className="integrity-toast-header">
        <span>Proctoring alerts</span>
        <button type="button" className="integrity-dismiss-all" onClick={onDismissAll}>
          Dismiss all
        </button>
      </div>
      {visible.map((n) => (
        <ToastItem key={n.id} notification={n} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
