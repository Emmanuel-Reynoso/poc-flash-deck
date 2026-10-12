import { useQueryClient } from '@tanstack/react-query';
import { absoluteUrl } from '../shared/clipboard';
import { TextDialog } from '../shared/ui/TextDialog';
import { filesApi } from './api';
import { slugify } from './paths';
import type { HtmlFile } from './types';

/** Lets the owner choose the last part of /u/{user}/{name}. */
export function EditLinkDialog({ file, onClose }: { file: HtmlFile; onClose: () => void }) {
  const queryClient = useQueryClient();
  return (
    <TextDialog
      title="Editar enlace"
      label="Nombre del enlace"
      initialValue={file.slug}
      submitLabel="Guardar enlace"
      maxLength={60}
      hint={(value) => {
        const slug = slugify(value);
        return (
          <>
            <p>
              {slug ? (
                <>
                  Va a quedar así:{' '}
                  <strong className="link-preview">{absoluteUrl(`/u/${file.ownerHandle}/${slug}`)}</strong>
                </>
              ) : (
                'Usá letras o números.'
              )}
            </p>
            <p>Al cambiarlo, los enlaces anteriores a este archivo (también los públicos) dejan de funcionar.</p>
          </>
        );
      }}
      onSubmit={async (slug) => {
        await filesApi.update(file.id, { slug });
        await queryClient.invalidateQueries({ queryKey: ['files'] });
      }}
      onClose={onClose}
    />
  );
}
