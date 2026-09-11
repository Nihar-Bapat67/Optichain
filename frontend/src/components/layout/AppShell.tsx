import { useEffect, useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Menu, X } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Button } from '../ui/Button';
import { ThemeToggle } from '../ui/ThemeToggle';
import { SidebarNav } from './Sidebar';
import { navItemFor, type PageKey } from './navigation';

export interface AppShellProps {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
  apiOk?: boolean;
  /** Page-specific controls rendered on the right of the topbar. */
  topbarActions?: ReactNode;
  children: ReactNode;
}

export function AppShell({
  activePage,
  onNavigate,
  apiOk,
  topbarActions,
  children,
}: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const current = navItemFor(activePage);

  // Close the mobile drawer on Escape.
  useEffect(() => {
    if (!drawerOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDrawerOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [drawerOpen]);

  function handleNavigate(page: PageKey) {
    onNavigate(page);
    setDrawerOpen(false);
  }

  return (
    <div className="min-h-screen bg-canvas">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[120] focus:rounded-md focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-accent-fg"
      >
        Skip to main content
      </a>

      {/* ── Desktop sidebar ── */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-sidebar border-r border-border bg-surface lg:block">
        <SidebarNav activePage={activePage} onNavigate={handleNavigate} apiOk={apiOk} />
      </aside>

      {/* ── Mobile drawer ── */}
      <AnimatePresence>
        {drawerOpen ? (
          <div className="fixed inset-0 z-50 lg:hidden">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={() => setDrawerOpen(false)}
              className="absolute inset-0 bg-black/50 backdrop-blur-[2px]"
            />
            <motion.aside
              role="dialog"
              aria-modal="true"
              aria-label="Navigation menu"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 420, damping: 38 }}
              className="absolute inset-y-0 left-0 w-sidebar border-r border-border bg-surface shadow-xl"
            >
              <Button
                size="sm"
                variant="ghost"
                iconOnly
                onClick={() => setDrawerOpen(false)}
                aria-label="Close navigation menu"
                className="absolute right-2 top-3.5 z-10"
                leadingIcon={<X className="h-4 w-4" />}
              />
              <SidebarNav activePage={activePage} onNavigate={handleNavigate} apiOk={apiOk} />
            </motion.aside>
          </div>
        ) : null}
      </AnimatePresence>

      {/* ── Content column ── */}
      <div className="lg:pl-sidebar">
        <header
          className={cn(
            'sticky top-0 z-20 flex h-topbar items-center gap-3 border-b border-border',
            'bg-surface/85 px-4 backdrop-blur-md sm:px-6',
          )}
        >
          <Button
            size="sm"
            variant="ghost"
            iconOnly
            className="lg:hidden"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation menu"
            aria-expanded={drawerOpen}
            leadingIcon={<Menu className="h-4 w-4" />}
          />

          <div className="min-w-0 flex-1">
            <h1 className="truncate font-display text-md font-semibold text-content">
              {current.label}
            </h1>
            <p className="hidden truncate text-2xs text-content-subtle sm:block">
              {current.description}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {topbarActions}
            <ThemeToggle />
          </div>
        </header>

        <main id="main-content" className="mx-auto max-w-content px-4 py-6 sm:px-6 sm:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
