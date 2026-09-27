import type {
  ProcessingStage,
  ProcessingStatus,
} from "@/types/api";

export const PROCESSING_STAGE_LABELS: Record<ProcessingStage, string> = {
  queued: "Waiting for processing",
  uploading: "Uploading video",
  validating: "Validating video",
  preprocessing: "Preparing video",
  detecting_players: "Detecting players",
  tracking_players: "Tracking movement",
  calibrating_field: "Calibrating the pitch",
  calculating_metrics: "Calculating statistics",
  persisting_results: "Saving analytics",
  completed: "Complete",
};

export const PROCESSING_STATUS: Record<
  ProcessingStatus,
  {
    label: string;
    variant: "neutral" | "info" | "success" | "danger" | "warning";
  }
> = {
  queued: { label: "Queued", variant: "neutral" },
  processing: { label: "Processing", variant: "info" },
  completed: { label: "Completed", variant: "success" },
  failed: { label: "Failed", variant: "danger" },
  cancelled: { label: "Cancelled", variant: "warning" },
};
