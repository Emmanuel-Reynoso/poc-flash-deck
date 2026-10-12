import { FilesList } from '../files/FilesList';
import { UploadZone } from '../files/upload/UploadZone';

export function HomePage() {
  return (
    <main className="page">
      <UploadZone />
      <h1 className="section-title">Mis archivos</h1>
      <FilesList />
    </main>
  );
}
