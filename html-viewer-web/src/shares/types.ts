/** A public link to one file, with an expiry date. */
export interface ShareLink {
  token: string;
  fileId: string;
  createdAt: string;
  expiresAt: string;
}

/** What anonymous viewers of a share link receive. */
export interface PublicFile {
  title: string;
  fileName: string;
  ownerName: string;
  sizeBytes: number;
  updatedAt: string;
}
