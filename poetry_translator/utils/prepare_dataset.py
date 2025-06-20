import os
import json
import sys
import pandas as pd
from typing import List, Dict, Tuple
import re
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from poetry_meter_detector.utils.preprocess import (
    clean_text, detect_stress_pattern, identify_meter, 
    load_ruaccent_model, analyze_rhythm, count_syllables_ru
)

class DatasetPreparator:
    def __init__(self):
        self.accentizer = load_ruaccent_model()
        if self.accentizer is None:
            print("Предупреждение: модель RuAccent не загружена. Будет использован упрощенный анализ.")

    def analyze_poem(self, text: str, lang: str = 'ru') -> Dict:
        if lang != 'ru':
            return {
                "meter": "неопределенный размер",
                "rhythm": []
            }

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return {
                "meter": "неопределенный размер",
                "rhythm": []
            }

        line_analyses = []
        all_stress_patterns = []
        
        for line in lines:
            clean_line = clean_text(line)
            if not clean_line.strip():
                continue
                
            try:
                stress_pattern = detect_stress_pattern(clean_line, language='ru', use_ruaccent=True, accentizer=self.accentizer)
                if not stress_pattern and self.accentizer is None:
                    words = clean_line.split()
                    stress_pattern = []
                    syllable_count = 0
                    for word in words:
                        syllables = count_syllables_ru(word)
                        if syllables > 0:
                            stress_pattern.append(syllable_count)
                        syllable_count += syllables
            except Exception as e:
                print(f"Ошибка при анализе строки '{line}': {e}")
                continue
                
            all_stress_patterns.extend(stress_pattern)
            
            meter = identify_meter(stress_pattern)
            rhythm_info = analyze_rhythm(stress_pattern)
            
            line_analyses.append({
                'line': line,
                'stress_pattern': stress_pattern,
                'meter': meter,
                'rhythm_info': rhythm_info
            })

        overall_meter = identify_meter(all_stress_patterns)
        
        return {
            "meter": overall_meter,
            "rhythm": all_stress_patterns,
            "line_analyses": line_analyses
        }

    def prepare_parallel_poems(self, source_file: str, target_file: str, 
                             source_lang: str = 'ru', target_lang: str = 'en') -> List[Dict]:
        with open(source_file, 'r', encoding='utf-8') as f:
            source_poems = [p.strip() for p in f.read().split('\n\n') if p.strip()]
            
        with open(target_file, 'r', encoding='utf-8') as f:
            target_poems = [p.strip() for p in f.read().split('\n\n') if p.strip()]
            
        if len(source_poems) != len(target_poems):
            raise ValueError("Количество стихотворений в файлах не совпадает")
            
        dataset = []
        for source, target in zip(source_poems, target_poems):
            source_analysis = self.analyze_poem(source, source_lang)
            
            dataset.append({
                "source_text": source,
                "target_text": target,
                "meter": source_analysis["meter"],
                "rhythm": source_analysis["rhythm"],
                "line_analyses": source_analysis.get("line_analyses", [])
            })
            
        return dataset

    def save_dataset(self, dataset: List[Dict], output_file: str):
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Подготовка датасета для перевода стихов')
    parser.add_argument('--source_file', type=str, required=True, help='Путь к файлу с исходными стихами')
    parser.add_argument('--target_file', type=str, required=True, help='Путь к файлу с переводами')
    parser.add_argument('--output_file', type=str, required=True, help='Путь для сохранения датасета')
    parser.add_argument('--source_lang', type=str, default='ru', help='Язык исходных стихов')
    parser.add_argument('--target_lang', type=str, default='en', help='Язык переводов')
    
    args = parser.parse_args()
    
    preparator = DatasetPreparator()
    dataset = preparator.prepare_parallel_poems(
        args.source_file,
        args.target_file,
        args.source_lang,
        args.target_lang
    )
    
    preparator.save_dataset(dataset, args.output_file)
    print(f"Датасет сохранен в {args.output_file}")
    print(f"Количество пар стихотворений: {len(dataset)}")

if __name__ == '__main__':
    main() 