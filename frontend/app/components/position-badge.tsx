const colorMap: Record<string, string> = {
  QB: "bg-qb/20 text-qb",
  RB: "bg-rb/20 text-rb",
  WR: "bg-wr/20 text-wr",
  TE: "bg-te/20 text-te",
};

export default function PositionBadge({ position }: { position: string }) {
  const colors = colorMap[position] || "bg-muted/20 text-muted";
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold ${colors}`}
    >
      {position}
    </span>
  );
}
