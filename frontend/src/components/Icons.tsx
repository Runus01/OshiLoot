export function PlayIcon() {
  return (
    <svg className="play-icon" viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">
      <circle cx="16" cy="16" r="14.5" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M13 10.5v11l9-5.5z" fill="currentColor" />
    </svg>
  );
}

export function ChevronIcon({ direction }: { direction: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path
        d={direction === "left" ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7"}
        fill="none"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function PauseIcon() {
  return (
    <svg className="play-icon" viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">
      <circle cx="16" cy="16" r="14.5" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M11.5 10.5h3v11h-3zM17.5 10.5h3v11h-3z" fill="currentColor" />
    </svg>
  );
}
