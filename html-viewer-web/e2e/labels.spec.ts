import { dragToLabel, expect, labelSection, modal, test, upload } from './fixtures';
import type { Page } from '@playwright/test';

async function addLabel(page: Page, name: string) {
  await page.getByLabel('Nombre de la nueva etiqueta').fill(name);
  await page.getByRole('button', { name: 'Agregar etiqueta' }).click();
  await expect(labelSection(page, name)).toBeVisible();
}

const labelHeader = (page: Page, name: string) => labelSection(page, name).locator('.label__header');

const rowIn = (page: Page, section: string, title: string) =>
  labelSection(page, section).locator('li.file').filter({ hasText: title });

test.describe('etiquetas', () => {
  test('arrastrar un archivo a una etiqueta lo mueve, y queda guardado', async ({ alicePage }) => {
    await upload(alicePage, 'ventas.html');
    await upload(alicePage, 'compras.html');
    await addLabel(alicePage, 'Proyecto Alfa');
    await addLabel(alicePage, 'Proyecto Beta');
    await expect(labelSection(alicePage, 'Sin etiqueta').locator('li.file')).toHaveCount(2);

    await dragToLabel(alicePage, 'ventas', 'Proyecto Alfa');
    await expect(rowIn(alicePage, 'Proyecto Alfa', 'ventas')).toBeVisible();

    await dragToLabel(alicePage, 'compras', 'Proyecto Beta');
    await expect(rowIn(alicePage, 'Proyecto Beta', 'compras')).toBeVisible();
    await expect(labelSection(alicePage, 'Sin etiqueta').locator('li.file')).toHaveCount(0);

    // From one label to the other.
    await dragToLabel(alicePage, 'ventas', 'Proyecto Beta');
    await expect(labelSection(alicePage, 'Proyecto Beta').locator('li.file')).toHaveCount(2);
    await expect(labelSection(alicePage, 'Proyecto Alfa')).toContainText('Arrastrá archivos acá.');

    await alicePage.reload();
    await expect(labelSection(alicePage, 'Proyecto Beta').locator('li.file')).toHaveCount(2);
    await expect(labelSection(alicePage, 'Proyecto Alfa').locator('li.file')).toHaveCount(0);
  });

  test('arrastrar de vuelta a "Sin etiqueta" lo saca', async ({ alicePage }) => {
    await upload(alicePage, 'ventas.html');
    await addLabel(alicePage, 'Proyecto Alfa');
    await dragToLabel(alicePage, 'ventas', 'Proyecto Alfa');
    await expect(rowIn(alicePage, 'Proyecto Alfa', 'ventas')).toBeVisible();

    await dragToLabel(alicePage, 'ventas', 'Sin etiqueta');
    await expect(rowIn(alicePage, 'Sin etiqueta', 'ventas')).toBeVisible();

    await alicePage.reload();
    await expect(rowIn(alicePage, 'Sin etiqueta', 'ventas')).toBeVisible();
  });

  test('varios movimientos seguidos sin esperar: queda el último', async ({ alicePage }) => {
    await upload(alicePage, 'ventas.html');
    await addLabel(alicePage, 'Proyecto Alfa');
    await addLabel(alicePage, 'Proyecto Beta');
    const select = alicePage.getByLabel('Etiqueta de ventas');

    // A network that delivers out of order: the earlier a change is sent, the longer it takes.
    // Sent all at once, the first one would arrive last and win.
    let answered = 0;
    let sent = 0;
    await alicePage.route('**/api/files/*', async (route) => {
      if (route.request().method() !== 'PATCH') return route.fallback();
      const delay = Math.max(0, 1200 - 300 * sent++);
      await new Promise((done) => setTimeout(done, delay));
      await route.continue();
    });
    alicePage.on('response', (response) => {
      if (response.request().method() === 'PATCH') answered += 1;
    });

    const moves = ['Proyecto Alfa', 'Proyecto Beta', 'Sin etiqueta', 'Proyecto Alfa', 'Sin etiqueta', 'Proyecto Beta'];
    for (const label of moves) await select.selectOption({ label });
    await expect(rowIn(alicePage, 'Proyecto Beta', 'ventas')).toBeVisible(); // shown at once

    // Once all of them reached the server, what is stored is the last one.
    await expect.poll(() => answered, { timeout: 30_000 }).toBe(moves.length);
    await alicePage.unrouteAll({ behavior: 'wait' });

    await alicePage.reload();
    await expect(rowIn(alicePage, 'Proyecto Beta', 'ventas')).toBeVisible();
    await expect(labelSection(alicePage, 'Proyecto Alfa').locator('li.file')).toHaveCount(0);
    await expect(labelSection(alicePage, 'Sin etiqueta').locator('li.file')).toHaveCount(0);
  });

  test('mover y cambiar la visibilidad casi a la vez conserva las dos cosas', async ({ alicePage }) => {
    await upload(alicePage, 'ventas.html');
    await addLabel(alicePage, 'Proyecto Alfa');

    await alicePage.getByLabel('Etiqueta de ventas').selectOption({ label: 'Proyecto Alfa' });
    await alicePage.locator('li.file').getByRole('button', { name: 'Solo yo' }).click();
    await expect(alicePage.locator('li.file').getByRole('button', { name: 'Organización' })).toBeVisible();

    await alicePage.reload();
    await expect(rowIn(alicePage, 'Proyecto Alfa', 'ventas')).toBeVisible();
    await expect(rowIn(alicePage, 'Proyecto Alfa', 'ventas').getByRole('button', { name: 'Organización' })).toBeVisible();
  });

  test('también se puede mover con el selector, sin arrastrar', async ({ alicePage }) => {
    await upload(alicePage, 'ventas.html');
    await addLabel(alicePage, 'Proyecto Alfa');

    await alicePage.getByLabel('Etiqueta de ventas').selectOption({ label: 'Proyecto Alfa' });
    await expect(rowIn(alicePage, 'Proyecto Alfa', 'ventas')).toBeVisible();

    await alicePage.getByLabel('Etiqueta de ventas').selectOption({ label: 'Sin etiqueta' });
    await expect(rowIn(alicePage, 'Sin etiqueta', 'ventas')).toBeVisible();
  });

  test('renombrar una etiqueta conserva sus archivos', async ({ alicePage }) => {
    await upload(alicePage, 'ventas.html');
    await addLabel(alicePage, 'Proyecto Alfa');
    await alicePage.getByLabel('Etiqueta de ventas').selectOption({ label: 'Proyecto Alfa' });
    await expect(rowIn(alicePage, 'Proyecto Alfa', 'ventas')).toBeVisible();

    await labelHeader(alicePage, 'Proyecto Alfa').getByRole('button', { name: 'Renombrar' }).click();
    const dialog = modal(alicePage, 'Renombrar etiqueta');
    await dialog.getByLabel('Nombre').fill('Cliente Norte');
    await dialog.getByRole('button', { name: 'Guardar' }).click();

    await expect(rowIn(alicePage, 'Cliente Norte', 'ventas')).toBeVisible();
    await expect(labelSection(alicePage, 'Proyecto Alfa')).toHaveCount(0);
  });

  test('eliminar una etiqueta no borra sus archivos', async ({ alicePage }) => {
    await upload(alicePage, 'ventas.html');
    await addLabel(alicePage, 'Proyecto Alfa');
    await addLabel(alicePage, 'Proyecto Beta');
    await alicePage.getByLabel('Etiqueta de ventas').selectOption({ label: 'Proyecto Alfa' });
    await expect(rowIn(alicePage, 'Proyecto Alfa', 'ventas')).toBeVisible();

    await labelHeader(alicePage, 'Proyecto Alfa').getByRole('button', { name: 'Eliminar' }).click();
    const dialog = modal(alicePage, 'Eliminar etiqueta');
    await expect(dialog).toContainText('Sus archivos no se borran');

    // Cancelling changes nothing.
    await dialog.getByRole('button', { name: 'Cancelar' }).click();
    await expect(rowIn(alicePage, 'Proyecto Alfa', 'ventas')).toBeVisible();

    await labelHeader(alicePage, 'Proyecto Alfa').getByRole('button', { name: 'Eliminar' }).click();
    await modal(alicePage, 'Eliminar etiqueta').getByRole('button', { name: 'Eliminar etiqueta' }).click();

    await expect(labelSection(alicePage, 'Proyecto Alfa')).toHaveCount(0);
    await expect(rowIn(alicePage, 'Sin etiqueta', 'ventas')).toBeVisible();
  });

  test('no permite dos etiquetas con el mismo nombre', async ({ alicePage }) => {
    await addLabel(alicePage, 'Proyecto Alfa');
    await alicePage.getByLabel('Nombre de la nueva etiqueta').fill('proyecto alfa');
    await alicePage.getByRole('button', { name: 'Agregar etiqueta' }).click();

    await expect(alicePage.getByText('Ya tenés una etiqueta con ese nombre.')).toBeVisible();
    await expect(alicePage.getByRole('region', { name: /^Etiqueta / })).toHaveCount(1);
  });

  test('sin etiquetas la lista se ve simple, sin secciones', async ({ alicePage }) => {
    await upload(alicePage, 'ventas.html');
    await expect(alicePage.getByRole('region')).toHaveCount(0);
    await expect(alicePage.getByLabel('Etiqueta de ventas')).toHaveCount(0);
  });
});
