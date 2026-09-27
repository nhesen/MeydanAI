export type RatingBand = "excellent" | "good" | "average" | "low";

export const PLAYER_RATING_BANDS: Record<
  RatingBand,
  { minimum: number; label: string; className: string }
> = {
  excellent: {
    minimum: 8,
    label: "Excellent",
    className: "bg-success-100 text-success-800",
  },
  good: {
    minimum: 7,
    label: "Good",
    className: "bg-brand-100 text-brand-800",
  },
  average: {
    minimum: 6,
    label: "Average",
    className: "bg-warning-100 text-warning-800",
  },
  low: {
    minimum: 0,
    label: "Low",
    className: "bg-danger-100 text-danger-800",
  },
};

export function getRatingBand(rating: number | null) {
  if (rating === null) return null;
  return Object.values(PLAYER_RATING_BANDS).find(
    (band) => rating >= band.minimum,
  )!;
}
