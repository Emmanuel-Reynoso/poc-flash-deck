import { useQueryClient } from '@tanstack/react-query';
import { TextDialog } from '../shared/ui/TextDialog';
import { labelsApi } from './api';
import type { Label } from './types';

export function RenameLabelDialog({ label, onClose }: { label: Label; onClose: () => void }) {
  const queryClient = useQueryClient();
  return (
    <TextDialog
      title="Renombrar etiqueta"
      label="Nombre"
      initialValue={label.name}
      submitLabel="Guardar"
      maxLength={50}
      hint="Sus archivos siguen adentro."
      onSubmit={async (name) => {
        await labelsApi.rename(label.id, name);
        await queryClient.invalidateQueries({ queryKey: ['labels'] });
      }}
      onClose={onClose}
    />
  );
}
