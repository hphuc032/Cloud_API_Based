import Navbar from './Navbar';

export default function AppLayout({ children }) {
  return (
    <div className="flex min-h-screen bg-canvas">
      <Navbar />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-8 py-8">{children}</div>
      </main>
    </div>
  );
}
