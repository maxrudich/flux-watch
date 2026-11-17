# Flux watch face (web)

Веб-копия циферблата Apple Watch **Flux** для второго монитора. Работает по `TZ.md`; все факты и референсы — там и в `reference/`.

**Онлайн:** https://maxrudich.github.io/flux-watch/ — на планшете «Поделиться → На экран «Домой»», откроется без панели браузера.

**Запуск:** открыть `index.html` двойным кликом (file://) или через любой статический сервер. Внешних зависимостей нет.
Клавиши: `F` полный экран · `M` на весь экран / как часы · `A` Always-On · `C` цвет · `H` 12/24 · `S` секунды тик / плавно · `G` сетка · `?` справка.
URL: `?t=02:37:19&speed=60&freeze=1&mode=fill|watch&aod=1&color=dynamic|0..8&h12=1&grid=1&smooth=1&ui=0`. `smooth=1` — секунды «Плавно» (непрерывный подъём заливки); по умолчанию «Тик» (шаг в секунду, ~200 мс). Выбор сохраняется в `localStorage` вместе с остальными настройками; Always-On всегда тикает.
Смена минуты — пружина (ζ 0.66, response 0.6 с, перелёт ≈ 6%, старт :59.85, цифра меняется в :00.000), считается от времени, поэтому `?t=`/`?speed=`/`?freeze=` детерминированы. При `prefers-reduced-motion` — короткий кроссфейд.

## Файлы
| Путь | Что |
|---|---|
| `index.html` | циферблат (SVG, без шрифтов и без `scale()` цифр) |
| `src/glyph.js` | параметрические монолинейные глифы 0–9 (порт `tools/fluxglyph.py`, проверка `node tools/check_glyph_port.mjs`) |
| `data/layouts.js` | 1440 раскладок: `[x, y, w, h(, {параметры формы})]` в u для слотов H1 H2 M1 M2 |
| `tools/extract.py` | извлечение раскладок из `reference/tdc_3_all_1440_grid.jpg` (`.venv/bin/python -I tools/extract.py`), отчёт `tools/extract_report.json`, правки `tools/overrides.json` |
| `tools/check_layouts.mjs` | проверка всех 1440 раскладок по реальным чернилам: глифы в боксе и поле контента, нет NaN, зазор между глифами ≥ 1.5u (`node tools/check_layouts.mjs [--known]`); известные касания эталона — в `tools/ink_contact_exceptions.json` |
| `tools/check_morph.mjs` | проверка пружинной смены минуты на всех 1440 переходах (пик перелёта и середина пути) |
| `tools/fix_ink_gaps.py` | находит минуты со слипшимися глифами (баг 01:34: бокс «4» заходил на 1u под «1»), подбирает боксы по IoU и пишет `boxes` в `tools/overrides.json`; потом `.venv/bin/python -I tools/extract.py` |
| `tools/glyphs.html` | лаборатория глифов (+ сверка с эталонными кропами) |
| `tools/verify.html` | приёмка: IoU по 1440 ячейкам, голдены |
| `tools/compare.html` | кадры циферблата против эталонов (02:37:19, 03:09, 03:10, Always-On) |
| `tools/goldens.py`, `tools/check_video.py` | голдены §4.8 из крупных кадров и из видео |
| `tools/glyph_params.json` | базовые параметры глифов (подгонка по эталонным кропам: `tools/_fit_run.py`, `_fitlab.py`) → `python tools/gen_glyph_params.py` вшивает в `src/glyph.js` |
| `tools/shots/` | скриншоты 1920×1080, 2560×1440, 3440×1440, 1080×1920 |
| `legacy/` | старая неудачная версия, не используется (не в git) |

Для `verify.html`, `compare.html`, `glyphs.html` нужен локальный сервер (canvas не читает картинки с file://): `python3 -m http.server`.

`reference/` (кадры и видео Apple с TDC) и `tools/shots/` не публикуются: лежат только локально, скрипты из `tools/` их ждут.
