import { RouterProvider } from 'react-router';
import { Toaster } from 'sonner';
import { router } from './routes';
import { MockDbProvider } from './data/mock-db';

export default function App() {
  return (
    <MockDbProvider>
      <RouterProvider router={router} />
      <Toaster position="top-right" richColors closeButton />
    </MockDbProvider>
  );
}
