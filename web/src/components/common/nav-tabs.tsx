'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Separator } from '@/components/ui/separator';

const navItems = [
  { label: 'Dashboard', href: '/' },
  { label: 'Layers', href: '/layers' },
  { label: '量化实验室', href: '/history' },
  { label: '今日看板', href: '/today' },
  { label: 'History V2', href: '/history-v2' },
  { label: 'Pools', href: '/pools' },
  { label: 'Reports', href: '/reports' },
  { label: 'Industry', href: '/industry-report' },
  { label: 'Archive', href: '/archive' },
];

export function NavTabs() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto sm:ml-4">
      <Separator orientation="vertical" className="mr-2 hidden h-4 sm:block" />
      {navItems.map((item, i) => (
        <span key={item.href} className="flex shrink-0 items-center">
          {i > 0 && <Separator orientation="vertical" className="h-3 mx-1 opacity-30" />}
          <Link
            href={item.href}
            className={cn(
              'whitespace-nowrap rounded-sm px-1.5 py-0.5 text-xs transition-colors',
              isActive(item.href)
                ? 'text-anchor-accent font-medium'
                : 'text-anchor-textMuted hover:text-anchor-text'
            )}
          >
            {item.label}
          </Link>
        </span>
      ))}
    </div>
  );
}
