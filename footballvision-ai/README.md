# FootballVision AI

Halı saha və yayım futbol videosundan oyunçu/komanda statistikası, heatmap, pas/şut/qol hadisələri, possession, highlight və maç hesabatı çıxaran production analitik modul.

MeydanAI platformasına worker kimi qoşulur; eyni zamanda müstəqil FastAPI servisi kimi işləyir.

## 1. Seçilən arxitektura

Araşdırılmış YOLO futbol repolarının praktik hissələri bir pipeline-da birləşdirilib; kod kor-koranə kopyalanmayıb.

| Mərhələ | Seçim | Mənbə ideya |
| --- | --- | --- |
| Detection | YOLOv8 / YOLO11, futbol class-ları, COCO fallback | Ultralytics + Roboflow player/ball modelləri |
| Player tracking | ByteTrack (`trackers`), IoU fallback | Roboflow Trackers + Supervision |
| Ball tracking | Kalman + qısa interpolasiya | manchado53, AdamNgazzou |
| ID repair | jersey hist + motion + team | Aviasole tagging / re-ID ehtiyacı |
| Team split | Lab torso clustering + temporal vote | Sohag016, MeydanAI demo |
| Homography | 4 nöqtə ilə metr kalibrasiyası; avtomatik kontur yalnız nisbi mövqe təxminidir | Sohag016, Tony-Luna |
| Camera motion | optical-flow sürüşmə kompensasiyası və kamera kəsilməsində yeni izləmə seqmenti | TrishamBP / donaldng05 |
| Events | min-frame state machine + confidence | Aviasole + predaaaasaaaaaaa |
| xG | məsafə, bucaq, qapıçı, müdaxilə | SofaScore-tipli sadə model |
| API / jobs | FastAPI + SQLite, Celery/Redis optional | production worker |

Halı saha default: **40×20 m**, sabit yuxarı kamera, sprint həddi 18 km/saat. 11v11 üçün `configs/config.yaml` içində `mode: 11v11`, `105×68` və `sprint_kmh: 24` seçin.

## 2. Quraşdırma

Python 3.10+ və FFmpeg.

```powershell
cd footballvision-ai
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

GPU: CUDA-lı PyTorch quraşdırın, `detection.device: auto` CUDA görsə `0` seçəcək. CPU-da `device: cpu` qoyun.

Xüsusi futbol çəkiləri `models/` qovluğuna qoyun və `configs/config.yaml` içində `detection.model` yolunu yazın. Class adları `player`, `goalkeeper`, `referee`, `ball` olduqda COCO `person` fallback-inə ehtiyac qalmır.

## 3. CLI demo

```powershell
.\.venv\Scripts\python -m app --video path\to\match.mp4 --output var\demo --config configs\config.yaml
```

Nəticə:

- `match_summary.json`
- `player_stats.csv` / `team_stats.csv` / `events.csv`
- `heatmaps/`
- `highlights/`
- `annotated_raw.mp4` və `minimap_raw.mp4`
- `match_report.html`

CLI izləmə zamanı `{"progress": 5, "message": "..."}` formatında JSON sətirləri verir. `match_summary.json` mənbənin FPS, ölçü, müddət, model və `calibrated` / `calibration_source` məlumatlarını saxlayır.

Kalibrasiya küncləri verilməyibsə heatmap və nisbi mövqelər yenə çıxarılır, amma metr məsafəsi və km/saat sürəti boş saxlanır. Ot konturu tam meydanın künclərini təsdiqləmir. Bu rejimdə hadisələr `estimated: true` kimi işarələnən ilkin AI təxminləridir. İzləmə ID-ləri oyunçuların adları və ya təsdiqlənmiş unikal şəxsiyyətləri deyil; örtülmə zamanı ID parçalana bilər.

4 GB GPU üçün `FOOTBALLVISION_BATCH=2` və `FOOTBALLVISION_IMAGE_SIZE=640` uyğundur. GPU yaddaşı çatmasa inference batch-i avtomatik kiçildilir. `FOOTBALLVISION_FRAME_STRIDE` artırıldıqda vizual video müddəti saxlanır. `FOOTBALLVISION_RENDER=0` və `FOOTBALLVISION_PLAYER_CLIPS=0` əlavə video çıxışlarını söndürür.

## 4. API

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8088
```

```powershell
curl -F "video=@clip.mp4" -F "calibration=[[0.08,0.92],[0.94,0.93],[0.82,0.18],[0.16,0.17]]" http://127.0.0.1:8088/analyze/upload
curl http://127.0.0.1:8088/analysis/{job_id}
curl http://127.0.0.1:8088/analysis/{job_id}/players
curl http://127.0.0.1:8088/analysis/{job_id}/events
curl http://127.0.0.1:8088/analysis/{job_id}/heatmap/1 --output heat.png
curl http://127.0.0.1:8088/analysis/{job_id}/highlights
curl http://127.0.0.1:8088/analysis/{job_id}/report --output report.html
```

Səhv ID düzəlişi:

```powershell
curl -X PATCH http://127.0.0.1:8088/analysis/{job_id}/tracks/7 -H "Content-Type: application/json" -d "{\"team\":\"home\",\"jersey\":10,\"name\":\"Elvin\"}"
```

Uzun video üçün Redis + Celery:

```powershell
docker compose up --build
```

Celery yoxdursa API eyni prosesdə `ThreadPoolExecutor` ilə işləyir.

## 5. Halı saha kamerası kalibrləməsi

1. Kameranı meydanın uzun tərəfində, yüksəkdə, zoom və pan olmadan sabitləyin. Bütün ot səthi kadrda olsun.
2. Real ölçünü ölçün (tipik 5v5: 30–40 × 16–20 m, qapı ~3 m).
3. İlk kadrda dörd küncü bu sırayla seçin: yaxın-sol `(0,0)`, yaxın-sağ `(length,0)`, uzaq-sağ `(length,width)`, uzaq-sol `(0,width)`.
4. Koordinatlar 0–1 aralığında (piksel / en, piksel / hündürlük) `calibration.points` və ya upload `calibration` formasındadır.
5. Görünməyən küncü təxmin etməyin. Manual rejimdə meydanın bütün dörd küncü görünməli və kamera sabit qalmalıdır; əks halda relative rejimi seçin.
6. Standart 11×11 meydanda hər kadr üzrə avtomatik xətt nöqtəsi kalibrasiyası mümkündür. Kamera kəsildikdə izləmə yeni seqmentə keçir. Geometrik yoxlamadan keçməyən hissələr sürət və məsafəyə daxil edilmir.

MeydanAI idarə səhifəsində bu parametrlər video seçildikdən sonra göstərilir. CLI üçün eyni konfiqurasiyanı `--calibration-json calibration.json` ilə ötürün:

```json
{"mode":"automatic","pitch_mode":"11v11","camera_mode":"broadcast","length_m":105,"width_m":68}
```

Ölçüləri real meydanla əvəz edin. Avtomatik şablon yalnız uzunluğu 90–120 m, eni 45–90 m olan 11×11 meydan üçündür. `manual` rejimində `camera_mode` `fixed` olmalı, `points` massivində dörd normallaşdırılmış künc verilməlidir. `relative` rejimi metr və km/saat hesablamır. Etibarlı ölçülən zaman və izləmə əhatəsi nəticəyə əlavə olunur.

## 6. Test

YOLO çəkisi olmadan sintetik 5v5 ssenari:

```powershell
.\.venv\Scripts\python -m pytest
```

## 7. MeydanAI inteqrasiyası

Worker prosesində:

```
FOOTBALLVISION_ENABLED=1
FOOTBALLVISION_ROOT=<repo>/footballvision-ai
FOOTBALLVISION_CONFIG=<repo>/footballvision-ai/configs/config.yaml
```

Local motion (MOG2) worker fallback olaraq qalır. Vision pipeline ayrıca prosesdə işləyir ki, `app` paket adı toqquşmasın.

İnteqrasiya oyunçu şəkillərini, bir neçə ayrı kadrdan OCR forma nömrəsi təkliflərini və kalibrasiyanın keyfiyyətini saxlayır. Forma nömrəsi şəxsin kimliyini təsdiq etmir: təşkilatçı şəkli heyətlə müqayisə edib oyunçu əlaqəsini təsdiqləyir. AI hadisələri də ayrıca təsdiq/rədd edilir.

## 8. Gələcək plan

- Uzun oyun videolarında keyfiyyətin və sürətin ayrıca ölçülməsi
- Broadcast replay/VAR filter (Aviasole)
- SigLIP team embedding (Gyokuken / Football-Vision)
- SAM2 occlusion (manchado53) GPU-only optional
- Learned event head (pass/shot) rule-based fallback üstündə
- PostgreSQL event store və SofaScore-tipli public match page


## Video validation (2026-10-25)

The default detector now uses a separate YOLO11n ball specialist at 1280px,
with sequential overlapping rescue crops. Player inference remains at 640px
for the 4GB GPU. Ball associations are motion-gated; extrapolated positions
cannot confirm possession. Possession requires several observed contacts and
rejects fast fly-bys using ball motion relative to the player's feet.

Pass candidates retain the last contact through flight and expire after 3.5s.
Image-space control transfers can suggest passes without claiming metric
coordinates or distance. Completed passes are exported once. Mere displacement
or a stationary ball no longer produces automatic dribble/restart labels.
Shirt clustering downweights brightness to reduce sun/shadow splits and resets
votes after refitting. Re-identification never mixes calibrated and relative
world coordinates or overlapping tracklets.

Sprint bouts require 1s, with 2km/h hysteresis, and break on measurement gaps.
Per-video conversion to 11v11 selects 24km/h (small-sided: 18km/h). These are
configured operational thresholds, not independently validated athletic metrics.

Ball model: https://huggingface.co/martinjolif/yolo-football-ball-detection
Author: martinjolif. Model license: AGPL-3.0. Base: Ultralytics YOLO11n.
SHA256: fb37942448e7de08745e8aab148d0794f680a738ddd55e5f17abe9ab2d6313fb
Worker bootstrap verifies this checksum before using downloaded weights.
Related approach: https://github.com/roboflow/sports

Exports now retain ball/player observations and the possession timeline for
repeatable diagnostics. `ball_observed_coverage` measures detection availability,
not correctness. Four visible completed passes in the supplied 18s clip were
recovered; its final long pass remains unresolved. A single clip does not
establish general production accuracy, and player names still need roster review.
