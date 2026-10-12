import { APP_URL, expect, fileId, fileRow, test, upload, viewerHeading } from './fixtures';

test.describe('ver un archivo', () => {
  test('la barra muestra título y dueño, y permite volver, copiar y descargar', async ({ alice, alicePage }) => {
    await upload(alicePage, 'Ventas Q3.html', 'Ventas');
    await alicePage.goto(`/u/${alice.handle}/ventas-q3`);
    await expect(viewerHeading(alicePage, 'Ventas')).toBeVisible();

    await expect(alicePage.getByText('Ventas Q3', { exact: true })).toBeVisible();
    await expect(alicePage.getByText(alice.email)).toBeVisible();
    await expect(alicePage.getByRole('link', { name: 'Descargar' })).toHaveAttribute('href', /rscd=attachment/);

    await alicePage.getByRole('button', { name: 'Copiar enlace' }).click();
    await expect(alicePage.getByRole('button', { name: 'Copiado' })).toBeVisible();
    expect(await alicePage.evaluate(() => navigator.clipboard.readText())).toBe(
      `${APP_URL}/u/${alice.handle}/ventas-q3`,
    );

    await alicePage.getByRole('link', { name: '← Mis archivos' }).click();
    await expect(alicePage).toHaveURL('/');
    await expect(fileRow(alicePage, 'Ventas Q3')).toBeVisible();
  });

  test('el HTML subido corre aislado: otro origen y sin acceso a la app', async ({ alice, alicePage }) => {
    await upload(alicePage, 'reporte.html');
    await alicePage.goto(`/u/${alice.handle}/reporte`);

    const frame = alicePage.locator('iframe.html-frame');
    await expect(frame).toHaveAttribute('sandbox', /allow-scripts/);
    await expect(frame).not.toHaveAttribute('sandbox', /allow-same-origin/);
    await expect(frame).not.toHaveAttribute('sandbox', /allow-top-navigation/);
    expect(new URL((await frame.getAttribute('src'))!).origin).not.toBe(APP_URL);
  });

  test('el enlace viejo por ids sigue abriendo', async ({ alice, alicePage }) => {
    await upload(alicePage, 'reporte.html', 'Reporte');
    await alicePage.goto(`/view/${alice.id}/${await fileId(alicePage, 'reporte')}`);
    await expect(viewerHeading(alicePage, 'Reporte')).toBeVisible();
  });

  test('el enlace público viejo (/share/token) sigue abriendo', async ({ alicePage, anonymousPage }) => {
    await upload(alicePage, 'reporte.html', 'Reporte');
    const id = await fileId(alicePage, 'reporte');
    const { token } = await (await alicePage.request.post(`/api/files/${id}/shares`, { data: { expiresInDays: 1 } })).json();

    await anonymousPage.goto(`/share/${token}`);
    await expect(viewerHeading(anonymousPage, 'Reporte')).toBeVisible();
  });

  test('una dirección que no existe lo dice', async ({ alice, alicePage, anonymousPage }) => {
    await alicePage.goto(`/u/${alice.handle}/no-existe`);
    await expect(alicePage.getByText('No existe o no tenés acceso.')).toBeVisible();

    await alicePage.goto('/cualquier/cosa/rara');
    await expect(alicePage.getByText('No encontramos esta página.')).toBeVisible();

    await anonymousPage.goto('/s/nadie/nada-AAAAAAAAAAAA');
    await expect(anonymousPage.getByText('Este enlace no existe o ya venció.')).toBeVisible();
  });
});
