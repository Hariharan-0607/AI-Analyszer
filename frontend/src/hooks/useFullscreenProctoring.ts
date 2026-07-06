import { useEffect, useRef } from 'react';

interface UseFullscreenProctoringOptions {
  enabled: boolean;
  onExit: () => void;
}

/** Request fullscreen during the exam and flag when the student leaves it. */
export function useFullscreenProctoring({ enabled, onExit }: UseFullscreenProctoringOptions) {
  const enteredFullscreenRef = useRef(false);
  const onExitRef = useRef(onExit);

  useEffect(() => {
    onExitRef.current = onExit;
  }, [onExit]);

  useEffect(() => {
    if (!enabled) return;

    const requestFullscreen = async () => {
      if (document.fullscreenElement) {
        enteredFullscreenRef.current = true;
        return;
      }
      try {
        await document.documentElement.requestFullscreen();
        enteredFullscreenRef.current = true;
      } catch {
        // User or browser blocked fullscreen — still listen for exit if they enter manually.
      }
    };

    const onFullscreenChange = () => {
      if (document.fullscreenElement) {
        enteredFullscreenRef.current = true;
        return;
      }

      if (enteredFullscreenRef.current) {
        onExitRef.current();
        enteredFullscreenRef.current = false;
        window.setTimeout(() => {
          if (enabled) {
            void requestFullscreen();
          }
        }, 600);
      }
    };

    void requestFullscreen();
    document.addEventListener('fullscreenchange', onFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', onFullscreenChange);
      if (document.fullscreenElement === document.documentElement) {
        void document.exitFullscreen().catch(() => {});
      }
    };
  }, [enabled]);
}
