import { APP_URL, expect, fileRow, makeOldStyle, modal, test, upload, viewerHeading } from './fixtures';

// Files uploaded before readable links existed have no link name stored.
test.describe('archivos subidos antes de los enlaces legibles', () => {
  test.beforeEach(async ({ alice, alicePage }) => {
    await upload(alicePage, 'JEV en acción.html', 'Inducción');
    await makeOldStyle(alicePage, alice, 'JEV en acción', 'jev-en-accion');
    await alicePage.reload();
  });

  test('reciben su enlace legible solos, y abre', async ({ alice, alicePage }) => {
    const link = `/u/${alice.handle}/jev-en-accion`;
    await expect(fileRow(alicePage, 'JEV en acción')).toContainText(link);

    await fileRow(alicePage, 'JEV en acción').getByRole('link', { name: 'JEV en acción' }).click();
    await expect(alicePage).toHaveURL(link);
    await expect(viewerHeading(alicePage, 'Inducción')).toBeVisible();
  });

  test('editar enlace muestra y guarda un enlace legible, nunca uno por ids', async ({ alice, alicePage }) => {
    await fileRow(alicePage, 'JEV en acción').getByRole('button', { name: 'Editar enlace' }).click();
    const dialog = modal(alicePage, 'Editar enlace');
    await expect(dialog.getByLabel('Nombre del enlace')).toHaveValue('jev-en-accion');
    await dialog.getByLabel('Nombre del enlace').fill('induccion a jev');

    await expect(dialog).toContainText(`${APP_URL}/u/${alice.handle}/induccion-a-jev`);
    await expect(dialog).not.toContainText('/view/');
    await dialog.getByRole('button', { name: 'Guardar enlace' }).click();

    await expect(fileRow(alicePage, 'JEV en acción')).toContainText(`/u/${alice.handle}/induccion-a-jev`);
    await alicePage.goto(`/u/${alice.handle}/induccion-a-jev`);
    await expect(viewerHeading(alicePage, 'Inducción')).toBeVisible();
  });

  test('copiar y compartir también dan enlaces legibles', async ({ alice, alicePage }) => {
    await expect(alicePage.locator('main')).not.toContainText('/view/');

    await fileRow(alicePage, 'JEV en acción').getByRole('button', { name: 'Copiar enlace' }).click();
    expect(await alicePage.evaluate(() => navigator.clipboard.readText())).toBe(
      `${APP_URL}/u/${alice.handle}/jev-en-accion`,
    );

    await fileRow(alicePage, 'JEV en acción').getByRole('button', { name: 'Compartir' }).click();
    await expect(alicePage.getByLabel('Enlace interno')).toHaveValue(`${APP_URL}/u/${alice.handle}/jev-en-accion`);
    await alicePage.getByRole('button', { name: 'Crear enlace' }).click();
    await expect(alicePage.getByText(/Vence el/)).toBeVisible();
    expect(await alicePage.evaluate(() => navigator.clipboard.readText())).toMatch(
      new RegExp(`/s/${alice.handle}/jev-en-accion-[A-Za-z0-9]{12}$`),
    );
  });

  test('siguen siendo privados para los demás', async ({ alice, alicePage, bobPage }) => {
    await expect(fileRow(alicePage, 'JEV en acción')).toBeVisible();
    await bobPage.goto(`/u/${alice.handle}/jev-en-accion`);
    await expect(bobPage.getByText('No existe o no tenés acceso.')).toBeVisible();
  });
});
