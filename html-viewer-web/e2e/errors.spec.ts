import { dragToLabel, expect, fileRow, labelSection, modal, test, upload } from './fixtures';
import type { Page } from '@playwright/test';

/** Makes the API fail for one kind of call, as if the server had a problem. */
async function failApi(page: Page, method: string, path: string) {
  await page.route(path, (route) =>
    route.request().method() === method
      ? route.fulfill({ status: 500, json: { error: { code: 'internal_error', message: 'Unexpected error.' } } })
      : route.continue(),
  );
}

const GENERIC = 'Algo salió mal. Probá de nuevo en un momento.';

test.describe('cuando algo falla, se avisa y no se pierde nada', () => {
  test.beforeEach(async ({ alicePage }) => {
    await upload(alicePage, 'reporte.html');
    await alicePage.getByLabel('Nombre de la nueva etiqueta').fill('Proyecto Alfa');
    await alicePage.getByRole('button', { name: 'Agregar etiqueta' }).click();
    await expect(labelSection(alicePage, 'Proyecto Alfa')).toBeVisible();
  });

  test('mover a una etiqueta: avisa en la página y el archivo vuelve a su lugar', async ({ alicePage }) => {
    await failApi(alicePage, 'PATCH', '**/api/files/*');
    await dragToLabel(alicePage, 'reporte', 'Proyecto Alfa');

    const notice = alicePage.getByRole('alert');
    await expect(notice).toContainText(GENERIC);
    await expect(labelSection(alicePage, 'Sin etiqueta').locator('li.file')).toHaveCount(1);
    await expect(labelSection(alicePage, 'Proyecto Alfa').locator('li.file')).toHaveCount(0);

    await notice.getByRole('button', { name: 'Cerrar aviso' }).click();
    await expect(alicePage.getByRole('alert')).toHaveCount(0);
  });

  test('renombrar: el error aparece dentro de la ventana, que queda abierta', async ({ alicePage }) => {
    await failApi(alicePage, 'PATCH', '**/api/files/*');
    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Renombrar' }).click();
    const dialog = modal(alicePage, 'Renombrar archivo');
    await dialog.getByLabel('Título').fill('Otro nombre');
    await dialog.getByRole('button', { name: 'Guardar' }).click();

    await expect(dialog.getByRole('alert')).toHaveText(GENERIC);
    await expect(dialog.getByLabel('Título')).toHaveValue('Otro nombre'); // what was typed is still there

    // Once the server recovers, the same window saves it.
    await alicePage.unroute('**/api/files/*');
    await dialog.getByRole('button', { name: 'Guardar' }).click();
    await expect(fileRow(alicePage, 'Otro nombre')).toBeVisible();
  });

  test('eliminar: si falla, el archivo sigue', async ({ alicePage }) => {
    await failApi(alicePage, 'DELETE', '**/api/files/*');
    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Eliminar' }).click();
    const dialog = modal(alicePage, 'Eliminar archivo');
    await dialog.getByRole('button', { name: 'Eliminar', exact: true }).click();

    await expect(dialog.getByRole('alert')).toHaveText(GENERIC);
    await dialog.getByRole('button', { name: 'Cancelar' }).click();
    await alicePage.reload();
    await expect(fileRow(alicePage, 'reporte')).toBeVisible();
  });

  test('eliminar etiqueta: si falla, la etiqueta sigue', async ({ alicePage }) => {
    await failApi(alicePage, 'DELETE', '**/api/labels/*');
    await labelSection(alicePage, 'Proyecto Alfa').locator('.label__header').getByRole('button', { name: 'Eliminar' }).click();
    const dialog = modal(alicePage, 'Eliminar etiqueta');
    await dialog.getByRole('button', { name: 'Eliminar etiqueta' }).click();

    await expect(dialog.getByRole('alert')).toHaveText(GENERIC);
    await dialog.getByRole('button', { name: 'Cancelar' }).click();
    await expect(labelSection(alicePage, 'Proyecto Alfa')).toBeVisible();
  });

  test('crear enlace público: el error aparece en la ventana de compartir', async ({ alicePage }) => {
    await failApi(alicePage, 'POST', '**/api/files/*/shares');
    await fileRow(alicePage, 'reporte').getByRole('button', { name: 'Compartir' }).click();
    await alicePage.getByRole('button', { name: 'Crear enlace' }).click();

    await expect(modal(alicePage, 'Compartir').getByText(GENERIC)).toBeVisible();
    await expect(alicePage.getByText('No hay enlaces públicos activos.')).toBeVisible();
  });

  test('si la lista no carga, se dice en lugar de mostrarla vacía', async ({ alicePage }) => {
    await failApi(alicePage, 'GET', '**/api/files');
    await alicePage.reload();

    await expect(alicePage.getByText(GENERIC)).toBeVisible({ timeout: 15_000 });
    await expect(alicePage.getByText('Todavía no subiste archivos.')).toHaveCount(0);
  });
});
