import { expect, fileRow, newUser, test, upload } from './fixtures';
import type { Page } from '@playwright/test';

/** The SWA emulator's fake sign-in form, filled like a person would. Returns the id it assigned. */
async function signInThroughForm(page: Page, email: string): Promise<string> {
  await expect(page).toHaveURL(/\/\.auth\/login\/aad/);
  // Typed key by key: the emulator's form only records what it sees on key presses.
  await expect(page.getByLabel('User ID')).not.toHaveValue('');
  const id = await page.getByLabel('User ID').inputValue();
  await page.getByLabel('Username').pressSequentially(email);
  await page.getByRole('button', { name: 'Login' }).click();
  return id;
}

test.describe('sesión', () => {
  test('entrar por el formulario de login lleva a mis archivos', async ({ anonymousPage: page, disposable }) => {
    const user = newUser('nueva');
    await page.goto('/');
    user.id = await signInThroughForm(page, user.email);
    disposable.push(user);

    await expect(page).toHaveURL('/');
    await expect(page.getByText(user.email)).toBeVisible();
    await expect(page.getByText('Todavía no subiste archivos.')).toBeVisible();

    await upload(page, 'reporte.html');
    await expect(fileRow(page, 'reporte')).toContainText(`/u/${user.handle}/reporte`);
  });

  test('un enlace abierto sin sesión vuelve al mismo lugar después del login', async ({ alice, alicePage, anonymousPage: page }) => {
    await upload(alicePage, 'informe.html', 'Informe');
    await fileRow(alicePage, 'informe').getByRole('button', { name: 'Solo yo' }).click();
    await expect(fileRow(alicePage, 'informe').getByRole('button', { name: 'Organización' })).toBeVisible();

    const link = `/u/${alice.handle}/informe`;
    await page.goto(link);
    await signInThroughForm(page, newUser('visita').email);

    await expect(page).toHaveURL(link);
    await expect(page.frameLocator('iframe.html-frame').getByRole('heading', { name: 'Informe' })).toBeVisible();
  });

  test('salir cierra la sesión', async ({ alicePage }) => {
    await upload(alicePage, 'reporte.html');
    await alicePage.getByRole('link', { name: 'Salir' }).click();

    await expect(alicePage).toHaveURL(/\/\.auth\/login\/aad/);
    expect((await alicePage.request.get('/api/files')).status()).toBe(401);
    await alicePage.goto('/');
    await expect(alicePage).toHaveURL(/\/\.auth\/login\/aad/);
  });
});
