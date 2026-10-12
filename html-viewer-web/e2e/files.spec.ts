import { expect, fileRow, modal, test, upload } from './fixtures';

test.describe('acciones sobre un archivo', () => {
  test('renombrar abre una ventana propia y cambia solo el título', async ({ alice, alicePage }) => {
    await upload(alicePage, 'reporte.html');

    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Renombrar' }).click();
    const dialog = modal(alicePage, 'Renombrar archivo');
    await expect(dialog.getByLabel('Título')).toHaveValue('reporte');
    await dialog.getByLabel('Título').fill('Ventas del trimestre');
    await dialog.getByRole('button', { name: 'Guardar' }).click();

    await expect(dialog).toHaveCount(0);
    await expect(fileRow(alicePage, 'Ventas del trimestre')).toContainText(`/u/${alice.handle}/reporte`); // same link
  });

  test('se puede cancelar con el botón o con Escape', async ({ alicePage }) => {
    await upload(alicePage, 'reporte.html');

    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Renombrar' }).click();
    await modal(alicePage, 'Renombrar archivo').getByLabel('Título').fill('No guardar');
    await modal(alicePage, 'Renombrar archivo').getByRole('button', { name: 'Cancelar' }).click();
    await expect(alicePage.getByRole('dialog')).toHaveCount(0);

    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Editar enlace' }).click();
    await modal(alicePage, 'Editar enlace').getByLabel('Nombre del enlace').fill('no-guardar');
    await alicePage.keyboard.press('Escape');
    await expect(alicePage.getByRole('dialog')).toHaveCount(0);

    await alicePage.reload();
    await expect(fileRow(alicePage, 'reporte')).toBeVisible();
    await expect(alicePage.getByText('no-guardar')).toHaveCount(0);
  });

  test('eliminar pide confirmación y avisa qué se pierde', async ({ alicePage }) => {
    await upload(alicePage, 'reporte.html');
    await upload(alicePage, 'otro.html');

    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Eliminar' }).click();
    const dialog = modal(alicePage, 'Eliminar archivo');
    await expect(dialog).toContainText('¿Eliminar reporte?');
    await expect(dialog).toContainText('Sus enlaces, internos y públicos, dejan de funcionar.');

    await dialog.getByRole('button', { name: 'Cancelar' }).click();
    await expect(fileRow(alicePage, 'reporte')).toBeVisible();

    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Eliminar' }).click();
    await modal(alicePage, 'Eliminar archivo').getByRole('button', { name: 'Eliminar', exact: true }).click();

    await expect(fileRow(alicePage, 'reporte')).toHaveCount(0);
    await expect(fileRow(alicePage, 'otro')).toBeVisible();
    await alicePage.reload();
    await expect(fileRow(alicePage, 'reporte')).toHaveCount(0);
  });

  test('un archivo eliminado ya no se abre con su enlace', async ({ alice, alicePage }) => {
    await upload(alicePage, 'reporte.html');
    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Eliminar' }).click();
    await modal(alicePage, 'Eliminar archivo').getByRole('button', { name: 'Eliminar', exact: true }).click();
    await expect(fileRow(alicePage, 'reporte')).toHaveCount(0);

    await alicePage.goto(`/u/${alice.handle}/reporte`);
    await expect(alicePage.getByText('No existe o no tenés acceso.')).toBeVisible();
  });
});
