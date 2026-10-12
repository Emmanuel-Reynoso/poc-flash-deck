import { expect, fileRow, modal, test, upload, viewerHeading } from './fixtures';

test.describe('enlaces legibles', () => {
  test('el archivo se abre en /u/{usuario}/{nombre}', async ({ alice, alicePage }) => {
    await upload(alicePage, 'Ventas Q3.html', 'Ventas del trimestre');
    const link = `/u/${alice.handle}/ventas-q3`;

    await expect(fileRow(alicePage, 'Ventas Q3')).toContainText(link);
    await fileRow(alicePage, 'Ventas Q3').getByRole('link', { name: 'Ventas Q3' }).click();

    await expect(alicePage).toHaveURL(link);
    await expect(viewerHeading(alicePage, 'Ventas del trimestre')).toBeVisible();
  });

  test('dos archivos con el mismo nombre reciben enlaces distintos', async ({ alice, alicePage }) => {
    await upload(alicePage, 'reporte.html');
    await upload(alicePage, 'reporte.html');

    await expect(alicePage.locator('li.file')).toHaveCount(2);
    await expect(alicePage.getByText(`/u/${alice.handle}/reporte-2`)).toBeVisible();
  });

  test('se puede personalizar el enlace, y el anterior deja de funcionar', async ({ alice, alicePage }) => {
    await upload(alicePage, 'reporte.html', 'Mi reporte');

    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Editar enlace' }).click();
    const dialog = modal(alicePage, 'Editar enlace');
    await dialog.getByLabel('Nombre del enlace').fill('Informe Final 2026');
    // The dialog shows the resulting link while typing, and warns about the old one.
    await expect(dialog).toContainText(`/u/${alice.handle}/informe-final-2026`);
    await expect(dialog).toContainText('los enlaces anteriores a este archivo');
    await dialog.getByRole('button', { name: 'Guardar enlace' }).click();

    await expect(dialog).toHaveCount(0);
    await expect(fileRow(alicePage, 'reporte')).toContainText(`/u/${alice.handle}/informe-final-2026`);

    await alicePage.goto(`/u/${alice.handle}/informe-final-2026`);
    await expect(viewerHeading(alicePage, 'Mi reporte')).toBeVisible();

    await alicePage.goto(`/u/${alice.handle}/reporte`);
    await expect(alicePage.getByText('No existe o no tenés acceso.')).toBeVisible();
  });

  test('no deja usar un nombre de enlace que ya tengo en otro archivo', async ({ alice, alicePage }) => {
    await upload(alicePage, 'uno.html');
    await upload(alicePage, 'dos.html');

    await fileRow(alicePage, 'dos').getByRole('button', { name: 'Editar enlace' }).click();
    const dialog = modal(alicePage, 'Editar enlace');
    await dialog.getByLabel('Nombre del enlace').fill('uno');
    await dialog.getByRole('button', { name: 'Guardar enlace' }).click();

    // The reason shows inside the dialog, which stays open to fix it.
    await expect(dialog.getByRole('alert')).toHaveText('Ya tenés otro archivo con ese nombre de enlace.');
    await dialog.getByRole('button', { name: 'Cancelar' }).click();
    await expect(dialog).toHaveCount(0);

    await expect(fileRow(alicePage, 'dos')).toContainText(`/u/${alice.handle}/dos`);
  });
});

test.describe('enlace público', () => {
  test('es legible, lo abre cualquiera, y solo con el sufijo exacto', async ({ alice, alicePage, anonymousPage }) => {
    await upload(alicePage, 'Ventas Q3.html', 'Ventas públicas');

    await fileRow(alicePage, 'Ventas Q3').getByRole('button', { name: 'Compartir' }).click();
    await alicePage.getByRole('button', { name: 'Crear enlace' }).click();
    await expect(alicePage.getByText(/Vence el/)).toBeVisible();
    const url = await alicePage.evaluate(() => navigator.clipboard.readText());

    const readable = new RegExp(`/s/${alice.handle}/ventas-q3-[A-Za-z0-9]{12}$`);
    expect(url).toMatch(readable);

    await anonymousPage.goto(url);
    await expect(viewerHeading(anonymousPage, 'Ventas públicas')).toBeVisible();
    await expect(anonymousPage.getByText(`Compartido por ${alice.email}`)).toBeVisible();

    // Knowing the user and the file name is not enough.
    const expired = anonymousPage.getByText('Este enlace no existe o ya venció.');
    for (const guess of [url.slice(0, -1) + (url.endsWith('A') ? 'B' : 'A'), url.replace(/-[A-Za-z0-9]{12}$/, '')]) {
      await anonymousPage.goto(guess);
      await expect(expired).toBeVisible();
      await expect(anonymousPage.locator('iframe')).toHaveCount(0);
    }
  });

  test('revocarlo lo cierra', async ({ alicePage, anonymousPage }) => {
    await upload(alicePage, 'reporte.html', 'Reporte');
    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Compartir' }).click();
    await alicePage.getByRole('button', { name: 'Crear enlace' }).click();
    await expect(alicePage.getByText(/Vence el/)).toBeVisible();
    const url = await alicePage.evaluate(() => navigator.clipboard.readText());

    await anonymousPage.goto(url);
    await expect(viewerHeading(anonymousPage, 'Reporte')).toBeVisible();

    await alicePage.getByRole('button', { name: 'Revocar' }).click();
    await expect(alicePage.getByText('No hay enlaces públicos activos.')).toBeVisible();

    await anonymousPage.goto(url);
    await expect(anonymousPage.getByText('Este enlace no existe o ya venció.')).toBeVisible();
  });
});
