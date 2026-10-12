import csv
import random

ports = ['Мурманск', 'СПб', 'Калининград']
types = ['dry', 'reefer', 'tank']

with open('data/containers.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'weight', 'port', 'type'])
    for i in range(50):
        writer.writerow([
            i,
            random.randint(5000, 25000),
            random.choice(ports),
            random.choice(types)
        ])

print("Создан data/containers.csv с 50 контейнерами")