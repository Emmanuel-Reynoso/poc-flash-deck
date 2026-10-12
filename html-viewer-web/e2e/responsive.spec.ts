import { expect, fileRow, labelSection, modal, test, upload } from './fixtures';

test.describe('en un teléfono', () => {
  test('todo entra en pantalla y las acciones se pueden usar', async ({ alicePage }) => {
    await alicePage.setViewportSize({ width: 390, height: 800 });
    await upload(alicePage, 'Un informe con un nombre bastante largo para la pantalla.html');
    await alicePage.getByLabel('Nombre de la nueva etiqueta').fill('Proyecto Alfa');
    await alicePage.getByRole('button', { name: 'Agregar etiqueta' }).click();
    await expect(labelSection(alicePage, 'Proyecto Alfa')).toBeVisible();

    const sideways = () => alicePage.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(await sideways()).toBeLessThanOrEqual(0);

    const title = 'Un informe con un nombre bastante largo para la pantalla';
    for (const name of ['Copiar enlace', 'Compartir', 'Renombrar', 'Editar enlace', 'Eliminar']) {
      await expect(fileRow(alicePage, title).getByRole('button', { name })).toBeInViewport();
    }

    await alicePage.getByLabel(`Etiqueta de ${title}`).selectOption({ label: 'Proyecto Alfa' });
    await expect(labelSection(alicePage, 'Proyecto Alfa').locator('li.file')).toHaveCount(1);

    await fileRow(alicePage, title).getByRole('button', { name: 'Editar enlace' }).click();
    const box = await modal(alicePage, 'Editar enlace').boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
    await expect(modal(alicePage, 'Editar enlace').getByRole('button', { name: 'Guardar enlace' })).toBeInViewport();
    expect(await sideways()).toBeLessThanOrEqual(0);
  });
});
