import { useQueryClient } from '@tanstack/react-query';
import { TextDialog } from '../shared/ui/TextDialog';
import { filesApi } from './api';
import type { HtmlFile } from './types';

export function RenameFileDialog({ file, onClose }: { file: HtmlFile; onClose: () => void }) {
  const queryClient = useQueryClient();
  return (
    <TextDialog
      title="Renombrar archivo"
      label="Título"
      initialValue={file.title}
      submitLabel="Guardar"
      maxLength={200}
      hint="Es el nombre que se ve en la lista y al abrirlo. El enlace no cambia."
      onSubmit={async (title) => {
        await filesApi.update(file.id, { title });
        await queryClient.invalidateQueries({ queryKey: ['files'] });
      }}
      onClose={onClose}
    />
  );
}
