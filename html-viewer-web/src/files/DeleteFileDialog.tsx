import { useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog } from '../shared/ui/ConfirmDialog';
import { filesApi } from './api';
import type { HtmlFile } from './types';

export function DeleteFileDialog({ file, onClose }: { file: HtmlFile; onClose: () => void }) {
  const queryClient = useQueryClient();
  return (
    <ConfirmDialog
      title="Eliminar archivo"
      confirmLabel="Eliminar"
      onConfirm={async () => {
        await filesApi.remove(file.id);
        await queryClient.invalidateQueries({ queryKey: ['files'] });
      }}
      onClose={onClose}
    >
      <p>
        ¿Eliminar <strong>{file.title}</strong>?
      </p>
      <p className="muted">Sus enlaces, internos y públicos, dejan de funcionar. No se puede deshacer.</p>
    </ConfirmDialog>
  );
}
