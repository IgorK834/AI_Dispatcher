'use client';

import * as RadixTabs from '@radix-ui/react-tabs';
import type { ReactNode } from 'react';
import { cn } from './cn';

export type TabItem = { value: string; label: string; content: ReactNode };

type TabsProps = {
  items: TabItem[];
  value: string;
  onValueChange: (value: string) => void;
  /** Accessible name of the tab list. */
  label: string;
};

export function Tabs({ items, value, onValueChange, label }: TabsProps) {
  return (
    <RadixTabs.Root value={value} onValueChange={onValueChange}>
      <RadixTabs.List aria-label={label} className="flex gap-1 border-b border-line">
        {items.map((item) => (
          <RadixTabs.Trigger
            key={item.value}
            value={item.value}
            className={cn(
              'min-h-11 px-4 text-sm font-semibold text-ink2 data-[state=active]:border-b-2 data-[state=active]:border-red data-[state=active]:text-red',
            )}
          >
            {item.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {items.map((item) => (
        <RadixTabs.Content key={item.value} value={item.value} className="pt-4">
          {item.content}
        </RadixTabs.Content>
      ))}
    </RadixTabs.Root>
  );
}
