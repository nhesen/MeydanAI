# YOLO futbol analizi — repo müqayisəsi

| Repo | Model/Tracker | Mövcud funksiyalar | Çatışmayanlar | Layihəyə götürülən |
| --- | --- | --- | --- | --- |
| [Sohag016/football-match-intelligence-yolo-tracking](https://github.com/Sohag016/football-match-intelligence-yolo-tracking) | YOLOv8 + ByteTrack | HSV/KMeans komanda, 4-nöqtə homography, sürət/məsafə spike filter, possession, pas, heatmap, minimap, CSV | Event dərinliyi yox, API/highlight/xG/re-ID yoxdur | Homography, spike-filtered physics, proximity possession, rule-based pass |
| [Mhmdwael77/ai-football-analytics](https://github.com/Mhmdwael77/ai-football-analytics) | YOLO11 + BoT-SORT | Rollar, kalibrləmə, taktika, possession, AI report | Production API və event store zəif | YOLO11 + BoT-SORT seçimi, role split |
| [aviasoletechnologies/football-event-detection](https://github.com/aviasoletechnologies/football-event-detection) | DL detection + MOT | 10 event növü, confidence, human tagging, replay/cut filter | Fiziki stats və heatmap ikinci planda | Timestamped events + confidence, manual ID correction, broadcast cut şüuru |
| [donaldng05/football-cv](https://github.com/donaldng05/football-cv) | YOLOv8 + ByteTrack | Camera motion, speed/distance, possession, team class | Shot/goal/xG/API yox | Camera motion compensation |
| [manchado53/AI-Driven-Soccer-Analysis](https://github.com/manchado53/AI-Driven-Soccer-Analysis) | YOLO + SAM2 + Kalman ball | Per-frame keypoint homography, zona possession, heatmap, coach stats | SAM2 ağırdır, FastAPI yox | Ayrı ball Kalman, zona grid, sabit kamera fokusu |
| [Tony-Luna/soccer-video-analytics](https://github.com/Tony-Luna/soccer-video-analytics) | Custom YOLOv8 | Goal polygon, HSV team UI, layout video, heatmap | Tam avtomatik deyil | Goal polygon / on-target, 2D layout |
| [Gyokuken/Football-Game-Analyzer-YOLO](https://github.com/Gyokuken/Football-game-analyzer) | YOLO + ByteTrack + SigLIP | Pass map, radar, heatmap, GUI | GUI-first, servis deyil | Radar minimap, pass visualization, ayrı ball model |
| [TrishamBP/football_analysis_yolo](https://github.com/TrishamBP/football_analysis_yolo) | YOLO + ByteTrack | Optical-flow camera, interpolasiya, stubs | Tutorial səviyyə, event yox | Ball interpolation, stub/cache thinking, camera flow |
| [mradovic38/football-analysis](https://github.com/mradovic38/football-analysis) | YOLO + keypoints | Voronoi, possession, speed, track storage | Event/xG/API yox | Pitch keypoints, track persistence |
| [AkshaySatasiya/Football-Analysis-System](https://github.com/AkshaySatasiya/Football-Analysis-System) | YOLO + KMeans | Team color, tracking | Abdella klonu, production yox | Jersey crop clustering |
| [MehrozShahid/Football-Video-Analysis](https://github.com/MehrozShahid/Football-Video-Analysis) | — | Public README boş | İstifadəyə yararlı kod yox | — |
| [predaaaasaaaaaaa/mult-agents-football-match-analyzer](https://github.com/predaaaasaaaaaaa/mult-agents-football-match-analyzer) | YOLOv8s + ByteTrack + LangGraph | Pass/tackle/interception, LLM report, Telegram | ID parçalanması (228 track), ball 47%, LLM asılı | Modular agents, tackle/interception rules, narrative report |

Heç bir repo eyni vaxtda halı-saha kalibrləməsi, FastAPI job API, highlight, xG, re-ID və MeydanAI ingest contract-ını vermir. FootballVision AI bu boşluğu doldurur.
