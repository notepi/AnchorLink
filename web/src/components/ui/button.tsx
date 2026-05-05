import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-sm text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-anchor-accent disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default:
          'bg-anchor-accent text-anchor-text hover:bg-anchor-accent/90',
        destructive:
          'bg-anchor-negative text-anchor-text hover:bg-anchor-negative/90',
        outline:
          'border border-anchor-border bg-transparent hover:bg-anchor-bgSecondary hover:text-anchor-text',
        secondary:
          'bg-anchor-bgSecondary text-anchor-textSecondary hover:bg-anchor-bgTertiary',
        ghost:
          'hover:bg-anchor-bgSecondary hover:text-anchor-text',
        link:
          'text-anchor-accent underline-offset-2 hover:underline',
      },
      size: {
        default: 'h-6 px-2',
        sm: 'h-5 px-1.5',
        lg: 'h-7 px-3',
        icon: 'h-5 w-5',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };