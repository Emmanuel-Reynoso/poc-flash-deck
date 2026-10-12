import { useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog } from '../shared/ui/ConfirmDialog';
import { labelsApi } from './api';
import type { Label } from './types';

export function DeleteLabelDialog({ label, fileCount, onClose }: { label: Label; fileCount: number; onClose: () => void }) {
  const queryClient = useQueryClient();
  return (
    <ConfirmDialog
      title="Eliminar etiqueta"
      confirmLabel="Eliminar etiqueta"
      onConfirm={async () => {
        await labelsApi.remove(label.id);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['labels'] }),
          queryClient.invalidateQueries({ queryKey: ['files'] }),
        ]);
      }}
      onClose={onClose}
    >
      <p>
        ¿Eliminar la etiqueta <strong>{label.name}</strong>?
      </p>
      <p className="muted">
        {fileCount > 0
          ? 'Sus archivos no se borran: pasan a “Sin etiqueta”.'
          : 'No tiene archivos adentro.'}
      </p>
    </ConfirmDialog>
  );
}
