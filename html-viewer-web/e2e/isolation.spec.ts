import { expect, fileRow, labelSection, test, upload, viewerHeading } from './fixtures';

const NO_ACCESS = 'No existe o no tenés acceso.';

test.describe('cada usuario ve lo suyo y no lo de otro', () => {
  test('la lista muestra solo mis archivos', async ({ alicePage, bobPage }) => {
    await upload(alicePage, 'ventas.html');
    await upload(bobPage, 'compras.html');

    await alicePage.reload();
    await expect(fileRow(alicePage, 'ventas')).toBeVisible();
    await expect(fileRow(alicePage, 'compras')).toHaveCount(0);

    await bobPage.reload();
    await expect(fileRow(bobPage, 'compras')).toBeVisible();
    await expect(fileRow(bobPage, 'ventas')).toHaveCount(0);
  });

  test('un usuario nuevo arranca sin archivos ni etiquetas de otros', async ({ alicePage, bobPage }) => {
    await upload(alicePage, 'ventas.html');
    await alicePage.getByLabel('Nombre de la nueva etiqueta').fill('Proyecto Alfa');
    await alicePage.getByRole('button', { name: 'Agregar etiqueta' }).click();
    await expect(labelSection(alicePage, 'Proyecto Alfa')).toBeVisible();

    await bobPage.reload();
    await expect(bobPage.getByText('Todavía no subiste archivos.')).toBeVisible();
    await expect(bobPage.locator('li.file')).toHaveCount(0);
    await expect(bobPage.getByText('Proyecto Alfa')).toHaveCount(0);
  });

  test('el enlace de un archivo privado no le abre a otro usuario', async ({ alice, alicePage, bobPage }) => {
    await upload(alicePage, 'secreto.html', 'Contenido secreto');
    const link = `/u/${alice.handle}/secreto`;

    await alicePage.goto(link);
    await expect(viewerHeading(alicePage, 'Contenido secreto')).toBeVisible();

    await bobPage.goto(link);
    await expect(bobPage.getByText(NO_ACCESS)).toBeVisible();
    await expect(bobPage.locator('iframe')).toHaveCount(0);
    await expect(bobPage.getByText('secreto')).toHaveCount(0); // not even the title leaks
  });

  test('tampoco con el enlace viejo por ids, ni poniendo su propio usuario', async ({ alice, bob, alicePage, bobPage }) => {
    await upload(alicePage, 'secreto.html');
    const { items } = await (await alicePage.request.get('/api/files')).json();
    const fileId = items[0].id as string;

    for (const link of [`/view/${alice.id}/${fileId}`, `/view/${bob.id}/${fileId}`, `/u/${bob.handle}/secreto`]) {
      await bobPage.goto(link);
      await expect(bobPage.getByText(NO_ACCESS)).toBeVisible();
      await expect(bobPage.locator('iframe')).toHaveCount(0);
    }
  });

  test('con visibilidad Organización otro lo puede ver, pero no aparece en su lista', async ({ alice, alicePage, bobPage }) => {
    await upload(alicePage, 'informe.html', 'Informe abierto');
    const link = `/u/${alice.handle}/informe`;

    await fileRow(alicePage, 'informe').getByRole('button', { name: 'Solo yo' }).click();
    await expect(fileRow(alicePage, 'informe').getByRole('button', { name: 'Organización' })).toBeVisible();

    await bobPage.goto(link);
    await expect(viewerHeading(bobPage, 'Informe abierto')).toBeVisible();
    await bobPage.goto('/');
    await expect(bobPage.getByText('Todavía no subiste archivos.')).toBeVisible();

    // Back to private: the same link closes again.
    await fileRow(alicePage, 'informe').getByRole('button', { name: 'Organización' }).click();
    await expect(fileRow(alicePage, 'informe').getByRole('button', { name: 'Solo yo' })).toBeVisible();
    await bobPage.goto(link);
    await expect(bobPage.getByText(NO_ACCESS)).toBeVisible();
  });

  test('otro usuario no puede modificar ni borrar mis cosas llamando a la API', async ({ alicePage, bobPage }) => {
    await upload(alicePage, 'secreto.html');
    await alicePage.getByLabel('Nombre de la nueva etiqueta').fill('Mía');
    await alicePage.getByRole('button', { name: 'Agregar etiqueta' }).click();
    await expect(labelSection(alicePage, 'Mía')).toBeVisible();

    const fileId = (await (await alicePage.request.get('/api/files')).json()).items[0].id as string;
    const labelId = (await (await alicePage.request.get('/api/labels')).json()).items[0].id as string;
    const before = await (await alicePage.request.get('/api/files')).json();

    // bobPage.request carries Bob's session cookie.
    const attempts = [
      bobPage.request.patch(`/api/files/${fileId}`, { data: { title: 'hackeado' } }),
      bobPage.request.patch(`/api/files/${fileId}`, { data: { visibility: 'org' } }),
      bobPage.request.patch(`/api/files/${fileId}`, { data: { labelId: null } }),
      bobPage.request.delete(`/api/files/${fileId}`),
      bobPage.request.get(`/api/files/${fileId}/shares`),
      bobPage.request.post(`/api/files/${fileId}/shares`, { data: { expiresInDays: 1 } }),
      bobPage.request.patch(`/api/labels/${labelId}`, { data: { name: 'hackeada' } }),
      bobPage.request.delete(`/api/labels/${labelId}`),
    ];
    for (const response of await Promise.all(attempts)) expect(response.status()).toBe(404);

    expect(await (await alicePage.request.get('/api/files')).json()).toEqual(before);
    await alicePage.reload();
    await expect(fileRow(alicePage, 'secreto')).toBeVisible();
    await expect(labelSection(alicePage, 'Mía')).toBeVisible();
  });

  test('sin sesión no se ve nada: pide iniciar sesión', async ({ alice, alicePage, anonymousPage }) => {
    await upload(alicePage, 'secreto.html');

    for (const path of ['/', `/u/${alice.handle}/secreto`]) {
      await anonymousPage.goto(path);
      await expect(anonymousPage).toHaveURL(/\/\.auth\/login\/aad/);
      await expect(anonymousPage.locator('iframe')).toHaveCount(0);
    }
    for (const path of ['/api/files', '/api/labels', `/api/u/${alice.handle}/secreto`]) {
      expect((await anonymousPage.request.get(path)).status()).toBe(401);
    }
  });
});
