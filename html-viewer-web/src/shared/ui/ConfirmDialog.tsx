import { useState, type ReactNode } from 'react';
import { errorMessage } from '../messages';
import { Dialog } from './Dialog';

interface Props {
  title: string;
  confirmLabel: string;
  /** Explains what will and will not be lost. */
  children: ReactNode;
  /** Rejecting keeps the dialog open and shows the reason. */
  onConfirm: () => Promise<unknown>;
  onClose: () => void;
}

/** A modal that asks before doing something that cannot be undone. */
export function ConfirmDialog({ title, confirmLabel, children, onConfirm, onClose }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  return (
    <Dialog title={title} onClose={onClose}>
      <div className="dialog__message">{children}</div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <footer className="dialog__footer">
        <button type="button" className="btn" onClick={onClose} autoFocus>
          Cancelar
        </button>
        <button
          type="button"
          className="btn btn--danger-solid"
          disabled={working}
          onClick={async () => {
            setWorking(true);
            setError(null);
            try {
              await onConfirm();
              onClose();
            } catch (err) {
              setError(errorMessage(err));
              setWorking(false);
            }
          }}
        >
          {confirmLabel}
        </button>
      </footer>
    </Dialog>
  );
}
