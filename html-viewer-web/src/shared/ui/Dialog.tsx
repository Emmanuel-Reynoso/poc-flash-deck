import { useEffect, useRef, type ReactNode } from 'react';

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** The one modal window of the app: every action that needs input or confirmation opens in it. */
export function Dialog({ title, onClose, children }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    // Guard: StrictMode runs effects twice in development.
    if (dialog.current && !dialog.current.open) dialog.current.showModal();
  }, []);

  return (
    <dialog
      ref={dialog}
      className="dialog"
      onClose={onClose}
      onClick={(e) => e.target === dialog.current && dialog.current?.close()}
    >
      <div className="dialog__body">
        <header className="dialog__header">
          <h2>{title}</h2>
          <button type="button" className="icon-button" aria-label="Cerrar" onClick={() => dialog.current?.close()}>
            ×
          </button>
        </header>
        {children}
      </div>
    </dialog>
  );
}
