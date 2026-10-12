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
1. Issues cleanup: закрыть #4 (DEAP), #11 (генетика DEAP), #13 (navaltoolbox) 
   с комментарием «заменено pymoo/NumPy».
2. Обновить Issue #16 (T02): 6 сущностей, ID 0 допустим.
3. Проверить Project Board.
4. Создать configs/vessel.json, limits.json, ports.json.
5. Начать T02: Container + тест → ContainerType → PortRotation → Slot → 
   Vessel → Plan. По коммиту на каждую сущность.
6. T04 (загрузчик) — ПОСЛЕ T02.

## Открытые вопросы
- Пороги крена/дифферента — уточнить у руководителя.
- Гидростатические параметры судна — TBD.

## Правила
- Источник правды: файлы в репо, не чат.
- Никаких хардкодов, всё через configs/.
- Перед задачей вставить этот файл в чат с ИИ.