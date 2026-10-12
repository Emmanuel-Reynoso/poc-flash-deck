export type Visibility = 'private' | 'org';

export interface HtmlFile {
  id: string;
  ownerId: string;
  ownerName: string;
  fileName: string;
  title: string;
  sizeBytes: number;
  visibility: Visibility;
  status: 'pending' | 'ready';
  createdAt: string;
  updatedAt: string;
  /** Readable link: /u/{ownerHandle}/{slug}. Empty on files older than readable links. */
  slug: string;
  ownerHandle: string;
  /** Label the owner filed it under; null when unlabeled or when viewing someone else's file. */
  labelId: string | null;
}

export interface UploadTicket {
  file: HtmlFile;
  uploadUrl: string;
  expiresAt: string;
  requiredHeaders: Record<string, string>;
}

/** Short-lived URLs to show or download a file. */
export interface ViewLink<F = HtmlFile> {
  file: F;
  viewUrl: string;
  downloadUrl: string;
  expiresAt: string;
}
