import random
import numpy as np
import matplotlib
matplotlib.use('Agg')  # чтобы работало без окна
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# 1. Модель судна: сетка 8 bays x 4 rows
N_BAYS = 8
N_ROWS = 4
MAX_WEIGHT_PER_CELL = 30000  # кг

cells = []
for bay in range(N_BAYS):
    for row in range(N_ROWS):
        cells.append({
            'id': len(cells),
            'bay': bay,
            'row': row,
            'max_load': MAX_WEIGHT_PER_CELL,
            'current_load': 0,
            'container_id': None
        })

# 2. Контейнеры: 20 штук
ports = ['Мурманск', 'СПб', 'Калининград']
containers = []
for i in range(20):
    containers.append({
        'id': i,
        'weight': random.randint(5000, 25000),
        'port': random.choice(ports)
    })

# 3. Эвристика: тяжёлые — первыми
containers_sorted = sorted(containers, key=lambda c: c['weight'], reverse=True)

for cont in containers_sorted:
    placed = False
    for cell in cells:
        if cell['container_id'] is None and cell['current_load'] + cont['weight'] <= cell['max_load']:
            cell['container_id'] = cont['id']
            cell['current_load'] = cont['weight']
            placed = True
            break
    if not placed:
        print(f"Контейнер {cont['id']} не поместился!")

# 4. Вывод результата
print("Схема загрузки:")
for cell in cells:
    if cell['container_id'] is not None:
        cont = next(c for c in containers if c['id'] == cell['container_id'])
        print(f"Ячейка bay={cell['bay']}, row={cell['row']}: контейнер {cont['id']}, вес {cont['weight']}, порт {cont['port']}")

# 5. Визуализация
grid = np.zeros((N_BAYS, N_ROWS))
port_colors = {'Мурманск': 1, 'СПб': 2, 'Калининград': 3}
for cell in cells:
    if cell['container_id'] is not None:
        cont = next(c for c in containers if c['id'] == cell['container_id'])
        grid[cell['bay'], cell['row']] = port_colors[cont['port']]

fig, ax = plt.subplots(figsize=(10, 6))
cmap = plt.cm.colors.ListedColormap(['white', 'red', 'blue', 'green'])
ax.imshow(grid, cmap=cmap, aspect='auto')
ax.set_xticks(range(N_ROWS))
ax.set_yticks(range(N_BAYS))
ax.set_xlabel('Row')
ax.set_ylabel('Bay')
ax.set_title('Схема загрузки (цвет = порт назначения)')

legend_elements = [
    Patch(facecolor='red', label='Мурманск'),
    Patch(facecolor='blue', label='СПб'),
    Patch(facecolor='green', label='Калининград')
]
ax.legend(handles=legend_elements, loc='upper right')
plt.savefig('result/loading_scheme.png', dpi=150, bbox_inches='tight')
print("Визуализация сохранена в result/loading_scheme.png")