"use client";

import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "quiet";

const CLASS: Record<Variant, string> = {
  primary: "action",
  ghost: "action action--ghost",
  quiet: "action action--quiet",
};

interface ActionProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  children: ReactNode;
}

/**
 * Une action dit exactement ce qui se passe quand on l'utilise, et garde le
 * même nom d'un bout à l'autre du parcours.
 */
export function Action({ variant = "primary", children, ...rest }: ActionProps) {
  return (
    <button type="button" className={CLASS[variant]} {...rest}>
      {children}
    </button>
  );
}

export function ActionLink({
  href,
  variant = "primary",
  children,
}: {
  href: string;
  variant?: Variant;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={CLASS[variant]}>
      {children}
    </Link>
  );
}
