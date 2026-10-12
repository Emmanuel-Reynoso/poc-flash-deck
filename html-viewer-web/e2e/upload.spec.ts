import { expect, fileRow, htmlWith, test, upload } from './fixtures';

const html = (name: string) => ({ name, mimeType: 'text/html', buffer: Buffer.from(htmlWith(name)) });

test.describe('subir archivos', () => {
  test('rechaza lo que no es HTML y lo explica', async ({ alicePage }) => {
    await alicePage
      .locator('input[type=file]')
      .setInputFiles({ name: 'notas.txt', mimeType: 'text/plain', buffer: Buffer.from('hola') });

    await expect(alicePage.getByText('Solo se aceptan archivos .html o .htm.')).toBeVisible();
    await expect(alicePage.locator('li.file')).toHaveCount(0);
  });

  test('rechaza archivos más grandes que el límite', async ({ alicePage }) => {
    await alicePage
      .locator('input[type=file]')
      .setInputFiles({ name: 'enorme.html', mimeType: 'text/html', buffer: Buffer.alloc(21 * 1024 * 1024, 'a') });

    await expect(alicePage.getByText('Supera los 20 MB.')).toBeVisible();
    await expect(alicePage.locator('li.file')).toHaveCount(0);
  });

  test('acepta .htm', async ({ alice, alicePage }) => {
    await alicePage.locator('input[type=file]').setInputFiles(html('viejo.htm'));
    await expect(fileRow(alicePage, 'viejo')).toContainText(`/u/${alice.handle}/viejo`);
  });

  test('varios a la vez con el mismo nombre: cada uno con su enlace', async ({ alice, alicePage }) => {
    await alicePage.locator('input[type=file]').setInputFiles([html('reporte.html'), html('reporte.html'), html('reporte.html')]);

    await expect(alicePage.locator('li.file')).toHaveCount(3);
    for (const slug of ['reporte', 'reporte-2', 'reporte-3']) {
      await expect(alicePage.getByText(`/u/${alice.handle}/${slug}`, { exact: false }).filter({ hasText: new RegExp(`/${slug}$`) })).toHaveCount(1);
    }
  });

  test('nombres con acentos, espacios y mayúsculas dan un enlace limpio', async ({ alice, alicePage }) => {
    await upload(alicePage, 'Informe Año 2026 (v2).html');
    await expect(fileRow(alicePage, 'Informe Año 2026 (v2)')).toContainText(`/u/${alice.handle}/informe-ano-2026-v2`);
  });

  test('"Limpiar" saca los terminados de la cola', async ({ alicePage }) => {
    await upload(alicePage, 'reporte.html');
    await expect(alicePage.getByText('Listo')).toBeVisible();
    await alicePage.getByRole('button', { name: 'Limpiar' }).click();
    await expect(alicePage.getByText('Listo')).toHaveCount(0);
    await expect(fileRow(alicePage, 'reporte')).toBeVisible();
  });

  test('lo subido sigue ahí al volver a entrar', async ({ alicePage }) => {
    await upload(alicePage, 'reporte.html');
    await alicePage.reload();
    await expect(fileRow(alicePage, 'reporte')).toBeVisible();
  });
});
