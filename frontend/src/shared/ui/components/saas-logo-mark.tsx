import type { SVGProps } from "react";

export function SaasLogoMark(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      viewBox="0 0 112 112"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <rect
        fill="var(--muted)"
        height="88"
        rx="12"
        transform="rotate(-8 28 16)"
        width="72"
        x="28"
        y="16"
      />
      <rect
        fill="var(--card)"
        height="92"
        rx="12"
        stroke="currentColor"
        strokeWidth="5"
        width="72"
        x="20"
        y="10"
      />
      <path
        d="M66 10h26v26L66 10Z"
        fill="var(--primary)"
        fillOpacity="0.12"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="5"
      />
      <rect fill="var(--border)" height="5" rx="2.5" width="38" x="36" y="42" />
      <rect fill="var(--border)" height="5" rx="2.5" width="28" x="36" y="58" />
      <path
        clipRule="evenodd"
        d="M59 70 77 52l18 18-18 18-18-18Zm11 0 7-7 7 7-7 7-7-7Z"
        fill="var(--primary)"
        fillRule="evenodd"
      />
    </svg>
  );
}
