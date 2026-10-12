# Дневник разработки

## 12.10.2026 — Старт практической части
- Создал структуру проекта (src, data, result, docs, notebooks).
- Настроил Git и связал локальную папку с GitHub.
- Реализовал эвристический алгоритм расстановки контейнеров (src/heuristic.py).
- Сгенерировал 2D-визуализацию схемы загрузки (result/loading_scheme.png).
- Добавил подписи контейнеров на схему (id + вес).
- Создал CSV с 50 тестовыми контейнерами (data/containers.csv).
- Разобрал пример DEAP onemax (notebooks/deap_onemax.py).
- **Итог дня:** 5 задач закрыто, эвристика работает, DEAP изучен.

## План на 13.10.2026
- Написать генетический алгоритм на DEAP (#11).
- Сделать сравнительный анализ эвристики и генетики (#12).
- Начать изучение navaltoolbox для расчёта остойчивости (#13).


---

## ⚠️ Устаревший план (12.10.2026)
План «Написать генетический алгоритм на DEAP (#11), сравнительный анализ (#12), navaltoolbox (#13)» **отменён**. 
Заменено утверждённой архитектурой: **pymoo (NSGA-II)**, остойчивость — **своя модель на NumPy**.

---

## 12.10.2026 (T01 — завершён, вечер)

### Сделано
- Окружение: Python 3.13, venv, библиотеки (numpy 2.5.4, pandas, matplotlib 3.11.2, pymoo 0.6.2, flask 3.1.3)
- Пакет stowage-optimization (pip install -e .)
- Структура: src/stowage/{domain,model,datagen,algorithms,storage,services,viz,web}
- Документация: docs/model.md, docs/decisions.md, docs/state.md
- Ветка migration/target-structure запушена
- Issues: T01 [#15 DONE], T02 [#16], T03 [#17], T04 [#18], T05–T08 созданы
- Project Board настроен
- README, PROGRESS.md обновлены

### Не сделано
- configs/vessel.json, limits.json, ports.json
- Issues cleanup (#4, #11, #13 закрыть)
- T02 сущности
- Перенос result/ → results/

### Следующий шаг
configs/ → T04 → T03 → T02

### Открытые вопросы
- Пороги крена/дифферента (у руководителя)
- Гидростатические параметры судна (TBD)