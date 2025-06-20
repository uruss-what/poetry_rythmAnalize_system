import os
import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from utils.preprocess import (
    clean_text, split_into_lines, 
    detect_stress_pattern, identify_meter, load_ruaccent_model,
    detect_stress_pattern_en, identify_meter_en, analyze_english_poem
)

def print_separator():
    """Выводит разделитель для лучшей читаемости"""
    print("\n" + "-" * 50 + "\n")

def analyze_with_ruaccent(lines, accentizer=None):
    results = []
    
    for i, line in enumerate(lines):
        clean_line = clean_text(line)
        
        if not clean_line.strip():
            continue
            
        stress_pattern = detect_stress_pattern(clean_line, language='ru', use_ruaccent=True, accentizer=accentizer)
        
        meter = identify_meter(stress_pattern)
        
        print(f"Строка {i+1}: '{line}'")
        print(f"Схема ударений: {stress_pattern}")
        print(f"Размер: {meter}")
        print("---")
        
        results.append({
            'line': line,
            'stress_pattern': stress_pattern,
            'meter': meter
        })
    
    return results

def analyze_english_text(lines):
    results = []
    
    text = "\n".join(lines)
    
    analysis = analyze_english_poem(text)
    
    print(f"Общий размер стихотворения: {analysis['overall_meter']}")
    print("Оценки для каждого размера:")
    for meter, score in analysis['overall_scores'].items():
        print(f"- {meter}: {score:.1f}%")
    print_separator()
    
    for i, line_analysis in enumerate(analysis['lines_analysis']):
        line = line_analysis['line']
        stress_pattern = line_analysis['stress_pattern']
        meter = line_analysis['meter']
        scores = line_analysis['scores']
        
        print(f"Строка {i+1}: '{line}'")
        print(f"Схема ударений: {stress_pattern}")
        print(f"Размер: {meter}")
        
        print("Оценки для размеров:")
        for m, s in scores.items():
            print(f"- {m}: {s:.1f}%")
        print("---")
        
        results.append(line_analysis)
    
    return results

def interactive_mode():
    
    print("Выберите язык стихотворения:")
    print("1. Русский")
    print("2. Английский")
    language_choice = input("Выберите опцию (1/2): ").strip()
    
    is_russian = language_choice.startswith("1")
    
    if is_russian:
        accentizer = load_ruaccent_model()
        if accentizer is None:
            print("Предупреждение: не удалось загрузить модель")
    
    print_separator()
    print("Введите стихотворение построчно. Для завершения введите пустую строку или 'exit'.")
    
    lines = []
    while True:
        line = input("> ")
        if line.strip() == "" or line.lower() == "exit":
            break
        lines.append(line)
    
    if not lines:
        print("Стихотворение не введено. Выход из программы.")
        return
    
    print_separator()
    
    print("Результаты анализа метрики стихотворения:")
    
    if is_russian:
        results = analyze_with_ruaccent(lines, accentizer=accentizer if 'accentizer' in locals() else None)
        
        print_separator()
        print("Итоговый результат:")
        
        if results:
            meter_count = {}
            for r in results:
                meter = r['meter']
                if meter in meter_count:
                    meter_count[meter] += 1
                else:
                    meter_count[meter] = 1
            
            most_common_meter = max(meter_count.items(), key=lambda x: x[1])
            print(f"Наиболее вероятный размер: {most_common_meter[0]} ({most_common_meter[1]}/{len(results)} строк)")
        else:
            print("Не удалось проанализировать ни одной строки.")
    else:
        results = analyze_english_text(lines)

if __name__ == "__main__":
    interactive_mode() 