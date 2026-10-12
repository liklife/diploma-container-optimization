import random
from deap import base, creator, tools, algorithms

# 1. Создаём фитнес-класс (максимизация)
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", list, fitness=creator.FitnessMax)

# 2. Настройка инструментов
toolbox = base.Toolbox()
toolbox.register("attr_bool", random.randint, 0, 1)
toolbox.register("individual", tools.initRepeat, creator.Individual, 
                 toolbox.attr_bool, 100)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

# 3. Фитнес-функция: считаем количество единиц
def evalOneMax(individual):
    return sum(individual),

toolbox.register("evaluate", evalOneMax)
toolbox.register("mate", tools.cxTwoPoint)
toolbox.register("mutate", tools.mutFlipBit, indpb=0.05)
toolbox.register("select", tools.selTournament, tournsize=3)

# 4. Запуск
population = toolbox.population(n=50)
result, log = algorithms.eaSimple(population, toolbox, 
                                   cxpb=0.5, mutpb=0.2, 
                                   ngen=20, verbose=True)

best = tools.selBest(population, 1)[0]
print(f"\nЛучшее решение: {sum(best)} единиц из 100")