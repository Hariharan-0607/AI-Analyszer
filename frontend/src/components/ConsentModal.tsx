interface ConsentModalProps {
  onAccept: () => void;
  onDecline: () => void;
}

export function ConsentModal({ onAccept, onDecline }: ConsentModalProps) {
  return (
    <div className="consent-overlay">
      <div className="consent-modal">
        <h2>Proctored Viva — Consent Required</h2>
        <p>
          Before starting your live viva, please read and accept the monitoring notice below.
        </p>
        <ul>
          <li>Your camera will be used for identity verification and attention monitoring.</li>
          <li>
            <strong>No raw video or audio is sent to the server.</strong> Face analysis runs
            entirely in your browser.
          </li>
          <li>
            Only lightweight integrity events are transmitted (e.g. gaze away, tab switch,
            face not detected).
          </li>
          <li>
            Only your <strong>built-in webcam</strong> may be used — switching cameras or using
            phone relay apps (DroidCam, Iriun, OBS virtual cam) is flagged.
          </li>
          <li>
            <strong>Phones, laptops, or extra screens</strong> visible in the camera are detected
            and flagged.
          </li>
          <li>
            During setup we <strong>calibrate gaze</strong> while you look at the screen center.
          </li>
          <li>
            The exam runs in <strong>fullscreen</strong>. Leaving fullscreen is flagged immediately.
          </li>
          <li>Screenshot shortcuts are detected and recorded as strikes.</li>
          <li>Tab switching may be flagged.</li>
          <li>Connection loss or camera denial will be recorded.</li>
        </ul>
        <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
          <button className="primary" onClick={onAccept}>
            I Consent — Start Viva
          </button>
          <button className="secondary" onClick={onDecline}>
            Decline
          </button>
        </div>
      </div>
    </div>
  );
}
