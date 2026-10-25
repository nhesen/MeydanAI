import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { AnalysisQuality } from "@/types/api";

export function AnalysisQualityPanel({ quality }: { quality?: AnalysisQuality }) {
  const source = quality?.source ?? "unavailable";
  const sourceLabel = /manual/i.test(source) ? "Manual pitch corners" : /keypoint|automatic|template/i.test(source) ? "Automatic pitch keypoints" : source === "unavailable" ? "Calibration unavailable" : source.replaceAll("_", " ");
  return (
    <Card className="mt-5">
      <h2 className="font-semibold text-slate-950">Analysis provenance</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant={quality?.physical_metrics_available ? "success" : "warning"}>{quality?.physical_metrics_available ? "Pitch-calibrated measurements" : "Distance and speed unavailable"}</Badge>
        <Badge>{sourceLabel}</Badge>
        <Badge variant={quality?.identity_mapping === "confirmed" ? "success" : "warning"}>{quality?.identity_mapping === "confirmed" ? "Player mapping reviewed" : quality?.identity_mapping === "estimated" ? "Player identities estimated" : "Player mapping unavailable"}</Badge>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        {quality?.physical_metrics_available ? "Distance and speed use pitch calibration and the configured dimensions. Tracking and camera visibility still affect the measurements." : "Physical measurements are withheld until reliable pitch calibration is available. Movement tracks can still be reviewed."}
        {quality?.pitch_length_m && quality.pitch_width_m ? ` Pitch: ${quality.pitch_length_m} × ${quality.pitch_width_m} m.` : ""}
        {quality?.identity_mapping !== "confirmed" ? " Player names and teams assigned to detected tracks need organizer review." : ""}
      </p>
      {quality?.physical_metrics_available && quality.calibration_coverage != null ? <p className="mt-2 text-xs leading-5 text-slate-500">Calibrated tracking coverage: {Math.round(quality.calibration_coverage * 100)}%{quality.measured_seconds != null ? ` · ${quality.measured_seconds.toFixed(1)} measured player-seconds` : ""}. Time is summed over the included player tracks. Physical metrics describe calibrated intervals only.</p> : null}
      {quality?.ball_observed_coverage != null ? <p className="mt-2 text-xs leading-5 text-slate-500">Ball directly detected in {Math.round(quality.ball_observed_coverage * 100)}% of analysed frames. This measures visibility, not event accuracy. Passes remain suggestions until reviewed; unresolved outcomes are omitted.</p> : null}
      {quality?.sprint_threshold_kmh != null && quality.sprint_min_duration_s != null ? <p className="mt-2 text-xs leading-5 text-slate-500">Sprint definition: at least {quality.sprint_threshold_kmh} km/h for {quality.sprint_min_duration_s} s, with a small tolerance for speed fluctuations. Measurement gaps break a sprint.</p> : null}
    </Card>
  );
}
