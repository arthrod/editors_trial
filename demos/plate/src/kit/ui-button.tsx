import * as React from 'react';

/**
 * The www app's `toc-static.tsx` uses a shadcn button. This demo ships no
 * component library, so the button is a plain element with the same API.
 */
export const Button = React.forwardRef<HTMLButtonElement, React.ComponentProps<'button'>>(
  function Button({ children, variant, size, ...props }, ref) {
    return (
      <button ref={ref} type="button" {...props}>
        {children}
      </button>
    );
  }
);

export const buttonVariants = {};
