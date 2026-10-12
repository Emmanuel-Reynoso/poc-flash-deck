import { Link, Outlet, Route, Routes } from 'react-router-dom';
import { AuthGate } from '../auth/AuthGate';
import { ViewerPage } from '../files/ViewerPage';
import { SharedPage } from '../shares/SharedPage';
import { HomePage } from './HomePage';
import { Layout } from './Layout';

function NotFound() {
  return (
    <div className="empty">
      <p>No encontramos esta página.</p>
      <Link to="/">Volver al inicio</Link>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      {/* Public: anyone with a valid token */}
      <Route path="/s/:handle/:slugAndToken" element={<SharedPage />} />
      <Route path="/share/:token" element={<SharedPage />} />

      {/* Signed-in users of the organization */}
      <Route
        element={
          <AuthGate>
            <Outlet />
          </AuthGate>
        }
      >
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
        </Route>
        <Route path="/u/:handle/:slug" element={<ViewerPage />} />
        <Route path="/view/:ownerId/:fileId" element={<ViewerPage />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
