import { useState, type ReactNode } from 'react';
import { errorMessage } from '../messages';
import { Dialog } from './Dialog';

interface Props {
  title: string;
  label: string;
  initialValue: string;
  submitLabel: string;
  maxLength?: number;
  /** Help text under the field; a function receives what is being typed. */
  hint?: ReactNode | ((value: string) => ReactNode);
  /** Rejecting keeps the dialog open and shows the reason. */
  onSubmit: (value: string) => Promise<unknown>;
  onClose: () => void;
}

/** A modal with one text field: rename a file, a label, a link. */
export function TextDialog({ title, label, initialValue, submitLabel, maxLength, hint, onSubmit, onClose }: Props) {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const clean = value.trim();

  return (
    <Dialog title={title} onClose={onClose}>
      <form
        className="dialog__form"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!clean) return;
          if (clean === initialValue) return onClose();
          setSaving(true);
          setError(null);
          try {
            await onSubmit(clean);
            onClose();
          } catch (err) {
            setError(errorMessage(err));
            setSaving(false);
          }
        }}
      >
        <label className="field">
          <span>{label}</span>
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onFocus={(e) => e.currentTarget.select()}
            maxLength={maxLength}
            autoFocus
          />
        </label>
        {hint && <div className="dialog__hint muted">{typeof hint === 'function' ? hint(value) : hint}</div>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <footer className="dialog__footer">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn--primary" disabled={saving || !clean}>
            {submitLabel}
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
