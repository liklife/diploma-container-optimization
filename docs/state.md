# Состояние проекта

**Дата:** 12.10.2026
**Ветка:** migration/target-structure
**Версия:** v0-prototype

## Сделано (T01)
- Окружение: Python 3.13, venv, numpy, pandas, matplotlib, pymoo, flask
- Пакет stowage-optimization (pip install -e .)
- Структура: src/stowage/{domain,model,datagen,algorithms,storage,services,viz,web}
- Документация: docs/model.md, docs/decisions.md, docs/state.md
- Ветка запушена, Issues T01–T08 созданы, Project Board настроен
- README, PROGRESS.md

## Не сделано
- configs/vessel.json, limits.json, ports.json
- Issues cleanup (#4, #11, #13 закрыть; #16 обновить)
- T02 сущности (Container, ContainerType, PortRotation, Slot, Vessel, Plan)
- T04 загрузчик конфигов (ПОСЛЕ T02, т.к. зависит от Vessel)

## План на 13.10.2026
1. CSV эталон: data/containers.csv → data/samples/containers_legacy.csv.
2. T01 проверить (не закрывать повторно): smoke-тест, pip install -e ., pytest, pip check.
3. Issues cleanup: комментарии к #4/#11/#13, #16 → 6 сущностей, #17 → зависимость от #16+#18, #18 → JSON + загрузчик.
4. Project Board — проверить вручную.
5. git mv result/ → results/.
6. Обновить decisions.md: box-barge, GA (физика ОТДЕЛЬНО от декодера), порты (СПб → Санкт-Петербург), id int, лимиты привязать к судну, bay/колонна, единицы _kg/_t, GM 0.15 — «общий критерий IMO, требует подтверждения».
7. configs/vessel.json, limits.json, ports.json.
8. T02: Container → ContainerType → PortRotation → Slot → Vessel → Plan.

## Открытые вопросы
- Пороги крена/дифферента — уточнить у руководителя.
- Гидростатические параметры судна — TBD.

## Правила
- Источник правды: файлы в репо, не чат.
- Никаких хардкодов, всё через configs/.
- Перед задачей вставить этот файл в чат с ИИ.