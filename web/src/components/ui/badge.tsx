import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-sm border px-1 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-anchor-accent',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-anchor-bgSecondary text-anchor-textSecondary hover:bg-anchor-bgTertiary',
        positive:
          'border-anchor-positive/20 bg-anchor-positive/10 text-anchor-positive',
        negative:
          'border-anchor-negative/20 bg-anchor-negative/10 text-anchor-negative',
        neutral:
          'border-anchor-border bg-anchor-bgSecondary text-anchor-textSecondary',
        outline:
          'text-anchor-textSecondary border-anchor-border',
        accent:
          'border-anchor-accent/20 bg-anchor-accent/10 text-anchor-accent',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };