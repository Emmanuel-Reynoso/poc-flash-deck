import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { errorMessage } from '../shared/messages';
import { labelsApi } from './api';

export function NewLabelForm() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');

  const create = useMutation({
    mutationFn: labelsApi.create,
    onSuccess: () => {
      setName('');
      return queryClient.invalidateQueries({ queryKey: ['labels'] });
    },
  });

  return (
    <form
      className="new-label"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) create.mutate(name);
      }}
    >
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Nueva etiqueta, por ejemplo un proyecto"
        aria-label="Nombre de la nueva etiqueta"
        maxLength={50}
      />
      <button type="submit" className="btn" disabled={create.isPending || !name.trim()}>
        Agregar etiqueta
      </button>
      {create.error && <p className="error small">{errorMessage(create.error)}</p>}
    </form>
  );
}
