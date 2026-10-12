import { TableClient } from '@azure/data-tables';
import { test as base, expect, request, type Browser, type BrowserContext, type Page } from '@playwright/test';
import { E2E_URL } from '../playwright.config';

export { expect };

/** Where the web under test is served; links the app builds start with this. */
export const APP_URL = E2E_URL;

export interface TestUser {
  id: string;
  email: string;
  /** Name that appears in this user's links: /u/{handle}/... */
  handle: string;
}

/** A user nobody else has: tests never see each other's data. */
export function newUser(name: string): TestUser {
  const unique = Math.random().toString(36).slice(2, 10);
  return { id: `e2e${name}${unique}`, email: `${name}${unique}@contoso.com`, handle: `${name}${unique}` };
}

/** Signs in the way the SWA emulator's fake login does: by setting its session cookie. */
export async function signedInContext(browser: Browser, user: TestUser): Promise<BrowserContext> {
  const context = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'] });
  await context.addCookies([{ name: SESSION_COOKIE, value: sessionOf(user), url: APP_URL }]);
  return context;
}

const SESSION_COOKIE = 'StaticWebAppsAuthCookie';

function sessionOf(user: TestUser): string {
  const principal = {
    identityProvider: 'aad',
    userId: user.id,
    userDetails: user.email,
    userRoles: ['anonymous', 'authenticated'],
  };
  return Buffer.from(JSON.stringify(principal)).toString('base64');
}

// Azurite's fixed, publicly documented development account.
const AZURITE =
  'DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;' +
  'AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;' +
  'TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;';
const table = (name: string) => TableClient.fromConnectionString(AZURITE, name, { allowInsecureConnection: true });

/** Id of the user's file with that title, straight from the API. */
export async function fileId(page: Page, title: string): Promise<string> {
  const { items } = (await (await page.request.get('/api/files')).json()) as { items: { id: string; title: string }[] };
  const found = items.find((f) => f.title === title);
  if (!found) throw new Error(`No file titled "${title}"`);
  return found.id;
}

/**
 * Rewrites a stored file the way the app left it before readable links existed:
 * no link name, no user name, nothing reserved. The API offers no way to do this.
 */
export async function makeOldStyle(page: Page, user: TestUser, title: string, slug: string): Promise<void> {
  const id = await fileId(page, title);
  await table('files').updateEntity({ partitionKey: user.id, rowKey: id, slug: '', ownerHandle: '' }, 'Merge');
  await table('slugs').deleteEntity(user.id, slug);
  await table('users').deleteEntity('owner', user.id);
  await table('users').deleteEntity('handle', user.handle);
}

/** Deletes every row of a partition. Only for the throwaway users of these tests. */
async function emptyPartition(tableName: string, partitionKey: string): Promise<void> {
  const client = table(tableName);
  const rows = client.listEntities({ queryOptions: { filter: `PartitionKey eq '${partitionKey}'` } });
  for await (const row of rows) await client.deleteEntity(row.partitionKey!, row.rowKey!);
}

const ignoreMissing = (error: { statusCode?: number }) => {
  if (error.statusCode !== 404) throw error;
};

/**
 * Removes everything a test user created, so runs leave nothing behind.
 * Files go through the API (it also deletes blobs and public links); the rest
 * has no API to delete it and is removed from the tables.
 */
export async function removeEverythingOf(user: TestUser): Promise<void> {
  const api = await request.newContext({
    baseURL: APP_URL,
    extraHTTPHeaders: { Cookie: `${SESSION_COOKIE}=${sessionOf(user)}` },
  });
  const { items: files } = (await (await api.get('/api/files')).json()) as { items: { id: string }[] };
  for (const file of files) await api.delete(`/api/files/${file.id}`);
  await api.dispose();

  for (const name of ['files', 'slugs', 'labels']) await emptyPartition(name, user.id);
  await table('users').deleteEntity('owner', user.id).catch(ignoreMissing);
  await table('users').deleteEntity('handle', user.handle).catch(ignoreMissing);
}

export const htmlWith = (heading: string) => `<!doctype html><title>${heading}</title><h1>${heading}</h1>`;

/** Uploads through the page, like a person choosing a file, and waits until it is listed. */
export async function upload(page: Page, fileName: string, heading = fileName): Promise<void> {
  await page.locator('input[type=file]').setInputFiles({
    name: fileName,
    mimeType: 'text/html',
    buffer: Buffer.from(htmlWith(heading)),
  });
  const title = fileName.replace(/\.html?$/i, '');
  await expect(fileRow(page, title)).toBeVisible();
}

export const fileRow = (page: Page, title: string) =>
  page.locator('li.file').filter({ has: page.getByRole('link', { name: title, exact: true }) });

/** Drags a file by its grip onto a label section, with real mouse moves as a person would. */
export async function dragToLabel(page: Page, title: string, label: string): Promise<void> {
  const row = fileRow(page, title);
  const section = labelSection(page, label);
  await section.locator('.label__header').scrollIntoViewIfNeeded();
  const from = await row.locator('.file__grip').boundingBox();
  const to = await section.locator('.label__header').boundingBox();
  if (!from || !to) throw new Error('Nothing to drag: the file or the label is not on screen.');
  const start = { x: from.x + from.width / 2, y: from.y + from.height / 2 };

  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  // The browser only starts a drag after the pointer actually travels.
  await page.mouse.move(start.x + 10, start.y + 10, { steps: 5 });
  await expect(row, 'el arrastre tiene que empezar').toHaveClass(/is-dragging/);
  const end = { x: to.x + to.width / 2, y: to.y + to.height / 2 };
  await page.mouse.move(end.x, end.y, { steps: 12 });
  await page.mouse.move(end.x + 4, end.y + 2, { steps: 2 }); // hover a little over the target, as a hand does
  await expect(section, 'la etiqueta tiene que marcarse como destino').toHaveClass(/is-over/);
  await page.mouse.up();
}

export const labelSection = (page: Page, name: string) =>
  page.getByRole('region', { name: name === 'Sin etiqueta' ? name : `Etiqueta ${name}`, exact: true });

/** The uploaded page is rendered inside the sandboxed iframe. */
export const viewerHeading = (page: Page, heading: string) =>
  page.frameLocator('iframe.html-frame').getByRole('heading', { name: heading });

/** The app's own modal window (never a browser prompt). */
export const modal = (page: Page, title: string) => page.getByRole('dialog').filter({ hasText: title });

/**
 * Things that must never happen on any page, whatever the test is about:
 * a native browser dialog, or an uncaught error (which leaves a blank page).
 */
function watchForBreakage(page: Page): () => void {
  const nativeDialogs: string[] = [];
  const crashes: string[] = [];
  page.on('dialog', (dialog) => {
    nativeDialogs.push(`${dialog.type()}: ${dialog.message()}`);
    void dialog.dismiss();
  });
  page.on('pageerror', (error) => crashes.push(error.message));
  return () => {
    expect(nativeDialogs, 'la app no debe usar prompt/confirm/alert del navegador').toEqual([]);
    expect(crashes, 'la página no debe tener errores sin atrapar').toEqual([]);
  };
}

interface Fixtures {
  /** Users to clean up when the test ends. alice and bob are added on their own. */
  disposable: TestUser[];
  alice: TestUser;
  bob: TestUser;
  alicePage: Page;
  bobPage: Page;
  /** No session at all. */
  anonymousPage: Page;
}

export const test = base.extend<Fixtures>({
  disposable: async ({}, use) => {
    const users: TestUser[] = [];
    await use(users);
    for (const user of users) await removeEverythingOf(user);
  },

  alice: async ({ disposable }, use) => {
    const user = newUser('alice');
    disposable.push(user);
    await use(user);
  },

  bob: async ({ disposable }, use) => {
    const user = newUser('bob');
    disposable.push(user);
    await use(user);
  },

  alicePage: async ({ browser, alice }, use) => {
    const context = await signedInContext(browser, alice);
    const page = await context.newPage();
    const assertHealthy = watchForBreakage(page);
    await page.goto('/');
    await use(page);
    assertHealthy();
    await context.close();
  },

  bobPage: async ({ browser, bob }, use) => {
    const context = await signedInContext(browser, bob);
    const page = await context.newPage();
    const assertHealthy = watchForBreakage(page);
    await page.goto('/');
    await use(page);
    assertHealthy();
    await context.close();
  },

  anonymousPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const assertHealthy = watchForBreakage(page);
    await use(page);
    assertHealthy();
    await context.close();
  },
});
