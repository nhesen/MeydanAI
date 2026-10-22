# MeydanAI — YOLO video demo

Bu demo layihənin daxilində ayrıca yerli tətbiqdir. PostgreSQL və əsas Next.js
tətbiqini başlatmaq lazım deyil. Mövcud OpenCV worker və production statistikası
dəyişdirilmir; demo nəticələri oyunçu hesablarına avtomatik yazılmır.

## Başlatmaq

Python 3.12+, FFmpeg və ilk dəfə asılılıqlar/model üçün internet lazımdır.
Windows PowerShell-də layihə qovluğundan:

```powershell
.\Start-YoloDemo.ps1
```

Brauzerdə http://127.0.0.1:8010 açın. Alternativ:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[demo,dev]'
.\.venv\Scripts\python -m uvicorn app.demo.main:app --host 127.0.0.1 --port 8010
```

Tətbiq yerli demo üçündür. Bir proses və bir worker istifadə edin; `--workers`
sayını artırmayın. Giriş sistemi yoxdur, internetə açmayın. Video, hesabat və
analiz nəticələri `backend/var/yolo-demo/<job-id>/` daxilində saxlanır; serveri
dayandırdıqdan sonra lazım olmayan iş qovluqlarını özünüz silə bilərsiniz.

## Demo axını

1. 20–60 saniyəlik aydın futbol videosu seçin. Limit 180 saniyə / 500 MB-dır.
   YouTube linki birbaşa qəbul olunmur; əldə etdiyiniz MP4 faylını yükləyin.
2. Yayım/hərəkətli kamerada kalibrasiyanı söndürülmüş saxlayın.
3. Sabit kamera, zoom və kadr keçidi olmayan görüntüdə metr/km/saat üçün
   kalibrasiyanı aktivləşdirin. Məlum ölçülü yerüstü düzbucaqlının künclərini
   ardıcıllıqla seçin: `(0,0)`, `(uzunluq,0)`, `(uzunluq,en)`, `(0,en)`.
   İlk iki nöqtə uzunluğu, ikinci və üçüncü nöqtə eni təyin edir. Tam meydançanın
   küncləri görünürsə onun həqiqi ölçülərini daxil edin. Görünməyən nöqtələri
   təxmin etməyin. Seçilmiş sahədən kənardakı aşkarlamalar hesablanmır.
4. “Analizə başla” düyməsini basın. Səhifə yeniləndikdə URL-dəki job ID ilə
   vəziyyət bərpa edilir. Server yenidən başladıqda yarımçıq işlər failed olur.
5. İzləmə ID-ləri ilə videoya baxın, cədvəli və trayektoriyanı yoxlayın.
   JSON, CSV və H.264 MP4 nəticələrini endirin.

## Nəticələrin mənası

- YOLO11n COCO modelinin `person` sinfi və BoT-SORT işlədilir. Bu, xüsusi
  futbolçu identifikasiyası modeli deyil; hakim/tamaşaçı da insan sayılır.
- `track_count` fərqli izləmə ID-lərinin sayıdır, unikal oyunçuların sayı deyil.
  Örtülmə, sürətli kamera hərəkəti və kadr keçidləri ID dəyişməsinə səbəb ola bilər.
- Görünmə müddəti aşkarlanan kadr sayı / FPS-dir. Əminlik YOLO-nun seçilmiş
  nümunələrdəki orta aşkarlama skorudur, identifikasiya düzgünlüyünün faizi deyil.
- Kalibrasiya yoxdursa məsafə/sürət JSON-da `null`, cədvəldə `—` olur.
- Kalibrasiya varsa bbox-un alt orta nöqtəsi homoqrafiya ilə metrə çevrilir.
  Təxminən hər 0.4 saniyədə mövqe götürülür. Örtülmə boşluqları və 45 km/saatdan
  yüksək sıçrayışlar hesablanmır; rədd edilən sıçrayışların sayı ayrıca verilir.
  Dəyərlər süni limitə sıxışdırılmır. 45 km/saat keyfiyyət filtridir və səhv
  kalibrasiyanı etibarlı etmir. Aşağı sürətli bbox titrəməsi yenə xəta yaradır.
- Məsafə yalnız etibarlı görünən hissələr üçündür. Orta sürətin məxrəci həmin
  hissələrin müddətidir. Bu, bütün oyun üzrə məsafə və ya GPS dəqiqliyi deyil.
- Zaman kadr indeksi / nominal FPS ilə hesablanır. Dəyişən FPS-li videonu əvvəlcə
  sabit FPS-ə çevirin. Nümunə: `ffmpeg -i input.mp4 -r 25 -an clip.mp4`.
- Qol, pas, topa sahibolma, forma nömrəsi, komanda və reytinq hesablanmır.
  Hərəkətli kamera üçün metr/km/saat ayrıca dinamik meydança kalibrasiyası tələb edir.

## Parametrlər

| Dəyişən | İlkin qiymət | Məna |
| --- | --- | --- |
| `DEMO_YOLO_MODEL` | `yolo11n.pt` | Yerli model yolu və ya Ultralytics model adı; COCO `person=0` tələb olunur |
| `DEMO_DEVICE` | `cpu` | CUDA uyğun PyTorch/GPU varsa `0` seçilə bilər |
| `DEMO_IMAGE_SIZE` | `960` | Inferensiya görüntü ölçüsü; uzaqdakı oyunçular üçün 1280 sınana bilər |
| `DEMO_MAX_SECONDS` | `180` | Video müddəti limiti |
| `DEMO_STORAGE_PATH` | `var/yolo-demo` | Yerli nəticə qovluğu |

Daha böyük `yolo11s.pt` modeli daha çox hesablama tələb edir; seçimi öz video
nümunənizlə ölçün. İlk analizdə model çəkiləri endirilə bilər.

## Yoxlama

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/test_yolo_demo.py
.\.venv\Scripts\python -m ruff check app/demo tests/test_yolo_demo.py
```

Testlər məlum trayektoriya üzrə ölçü vahidlərini, kalibrasiya olmadan null
nəticələri, boşluq/sıçrayışları, giriş yoxlamasını və job axınını yoxlayır.
API testində inferensiya əvəzlənir; modelin real dəqiqliyi ayrıca futbol
videosunda yoxlanmalıdır.

### Bu nüsxədə aparılan sınaq — 28 sentyabr 2026

- Bütün backend testləri: **89 keçdi**, bunlardan 12-si yeni demo testidir.
- Demo Python kodu Ruff və mypy yoxlamalarından keçdi.
- Roboflow-un [rəsmi futbol nümunələrinin siyahısından](https://github.com/roboflow/sports/blob/main/examples/soccer/setup.sh)
  `08fd33_0.mp4` videosunun ilk 6 saniyəsi, 25 FPS: **150 kadr** real YOLO ilə analiz edildi.
- YOLO11n, BoT-SORT, 960 ölçü, CPU: model yerli olduqda təxminən **20 saniyə**.
  Bu yalnız bu kompüterdəki sınaqdır; ilk endirmə əlavə vaxt tələb edir.
- **63 izləmə ID-si**, eyni kadrda maksimum **28 ID** alındı. Bunlar 63/28 futbolçu
  demək deyil: bəzi ID-lər parçalanır, hakim və kənardakı insanlar da aşkarlanır.
- Kalibrasiya verilmədiyi üçün bütün metr/km/saat sahələri `null` qaldı.
- Nəticə videosu FFprobe ilə yoxlandı: H.264, 1280×720, 25 FPS, 6 saniyə.
- Sürət/məsafənin real meydança və GPS ilə müqayisəli dəqiqlik sınağı aparılmayıb.
  Ümumi insan modelini futbol üçün xüsusi təlim keçmiş modellə əvəz etmək
  və oyunçu ID-lərinin sabitliyini qiymətləndirmək növbəti keyfiyyət mərhələsidir.

Ultralytics proqramı və modelləri üçün AGPL-3.0 / Enterprise şərtləri tətbiq
olunur: https://www.ultralytics.com/license. Yayım və kommersiya istifadəsindən
əvvəl uyğun lisenziyanı seçin.
