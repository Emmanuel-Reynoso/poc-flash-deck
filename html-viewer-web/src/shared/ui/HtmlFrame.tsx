/**
 * Renders an uploaded HTML file in an isolated iframe.
 *
 * Two layers keep user content away from the app:
 *  1. The file is served from the Blob Storage origin, never from the app's origin.
 *  2. `sandbox` without `allow-same-origin` gives the page an opaque origin: its
 *     scripts run, but it cannot read cookies or storage, nor touch the parent page,
 *     nor navigate the top window.
 * Trade-off: pages that rely on localStorage/cookies may not work fully.
 */
const SANDBOX = 'allow-scripts allow-popups allow-forms allow-modals allow-downloads';

export function HtmlFrame({ src, title }: { src: string; title: string }) {
  return <iframe className="html-frame" src={src} title={title} sandbox={SANDBOX} referrerPolicy="no-referrer" allow="" />;
}
