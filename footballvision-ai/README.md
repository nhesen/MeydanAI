# FootballVision AI

Halı saha və yayım futbol videosundan oyunçu/komanda statistikası, heatmap, pas/şut/qol hadisələri, possession, highlight və maç hesabatı çıxaran production analitik modul.

MeydanAI platformasına worker kimi qoşulur; eyni zamanda müstəqil FastAPI servisi kimi işləyir.

## 1. Seçilən arxitektura

Araşdırılmış YOLO futbol repolarının praktik hissələri bir pipeline-da birləşdirilib; kod kor-koranə kopyalanmayıb.

| Mərhələ | Seçim | Mənbə ideya |
| --- | --- | --- |
| Detection | YOLOv8 / YOLO11, futbol class-ları, COCO fallback | Ultralytics + Roboflow player/ball modelləri |
| Player tracking | ByteTrack / BoT-SORT, IoU fallback | Supervision, TrishamBP, donaldng05 |
| Ball tracking | Kalman + qısa interpolasiya | manchado53, AdamNgazzou |
| ID repair | jersey hist + motion + team | Aviasole tagging / re-ID ehtiyacı |
| Team split | Lab torso clustering + temporal vote | Sohag016, MeydanAI demo |
| Homography | 4 nöqtə (sabit kamera) və ya avtomatik ot konturu | Sohag016, Tony-Luna |
| Camera motion | optical-flow homography, uğursuz olanda zəncir kəsilir | TrishamBP / donaldng05 |
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
5. Görünməyən küncü təxmin etməyin. Yalnız görünən düzbucaqlını kalibrləyin və `length_m`/`width_m` dəyərlərini həmin görünən sahəyə uyğun yazın.
6. Titəmə və kəsmə varsa `camera_mode: broadcast` və `compensate_camera: true`. Uğursuz qeydiyyat zənciri kəsilir; köhnə homography səssiz təkrar istifadə olunmur.

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

## 8. Gələcək plan

- Roboflow football-players + pitch-keypoint çəkilərinin default model kimi paylanması
- Jersey OCR ilə oyunçu nömrəsi
- Broadcast replay/VAR filter (Aviasole)
- SigLIP team embedding (Gyokuken / Football-Vision)
- SAM2 occlusion (manchado53) GPU-only optional
- Learned event head (pass/shot) rule-based fallback üstündə
- PostgreSQL event store və SofaScore-tipli public match page
