import re
import os
import json
import sys
import warnings

site_packages = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'Python', 'Python313', 'site-packages')
if os.path.exists(site_packages) and site_packages not in sys.path:
    sys.path.append(site_packages)
    print(f"Добавлен путь к site-packages в preprocess.py: {site_packages}")

try:
    from ruaccent import RUAccent
    RUACCENT_AVAILABLE = True
except ImportError as e:
    RUACCENT_AVAILABLE = False
    warnings.warn(f"Библиотека не установлена: {e}. Программа не сможет работать корректно.")

def clean_text(text):
    text = text.replace('\r\n', ' ').replace('\n', ' ')
    
    while '  ' in text:
        text = text.replace('  ', ' ')
    
    return text

def split_into_lines(text):
    lines = re.split(r'[.!?]+', text)
    
    lines = [line.strip() for line in lines if line.strip()]
    
    return lines

def count_syllables_ru(word):
    vowels = 'аеёиоуыэюя'
    
    count = sum(1 for char in word.lower() if char in vowels)
    
    return max(1, count)

def clean_word(word):
    if not word:
        return ""
        
    word = word.lower()
    
    word = re.sub(r'[^\w\s]', '', word)
    
    return word

def detect_stress_pattern(line, language='ru', use_ruaccent=True, accentizer=None):
    if not line.strip() or language != 'ru':
        return []
    
    line = line.lower()
    line = clean_text(line)
    words = line.split()
    
    if accentizer is None:
        accentizer = load_ruaccent_model()
    
    if accentizer:
        try:
            stressed_line = accentizer.process_all(line)
            if isinstance(stressed_line, list) and len(stressed_line) > 0:
                stressed_line = stressed_line[0]
            print(f"Проакцентированная строка: {stressed_line}")
            
            stressed_words = stressed_line.split()
            original_words = line.split()
            
            if len(stressed_words) == len(original_words):
                pattern = []
                syllable_count = 0
                vowels_ru = 'аеёиоуыэюя'
                
                for i, (word, stressed_word) in enumerate(zip(original_words, stressed_words)):
                    syllables_in_word = count_syllables_ru(word)
                    stressed_vowel_idx = -1
                    
                    plus_pos = stressed_word.find('+')
                    if plus_pos >= 0 and plus_pos < len(stressed_word):
                        vowel_count = 0
                        for j in range(plus_pos):
                            if stressed_word[j] in vowels_ru:
                                vowel_count += 1
                        
                        stressed_vowel_idx = vowel_count
                        
                    if stressed_vowel_idx >= 0:
                        pattern.append(syllable_count + stressed_vowel_idx)
                        
                    syllable_count += syllables_in_word
                
                return pattern
        except Exception as e:
            print(f"Ошибка при использовании RuAccent: {e}")
    
    print("Не удалось определить ударения с помощью RuAccent.")
    return []

def identify_meter(stress_pattern):
    if not stress_pattern or len(stress_pattern) < 2:
        return "неопределенный размер"


    max_pos = max(stress_pattern) if stress_pattern else 0
    binary_pattern = [0] * (max_pos + 1)
    for pos in stress_pattern:
        binary_pattern[pos] = 1
    

    meters = {
        'ямб': [0, 1],
        'хорей': [1, 0],
        'дактиль': [1, 0, 0],
        'амфибрахий': [0, 1, 0],
        'анапест': [0, 0, 1]
    }
    
    line_length = len(binary_pattern)
    
    meter_scores = {}
    
    for meter_name, meter_pattern in meters.items():
        meter_length = len(meter_pattern)
        score = 0
        total = 0
        
        for i in range(line_length):
            expected_stress = meter_pattern[i % meter_length]
            actual_stress = binary_pattern[i]
            
            if expected_stress == actual_stress:
                score += 1
            total += 1
        
        match_percentage = (score / total) * 100
        meter_scores[meter_name] = match_percentage
    
    intervals = []
    for i in range(1, len(stress_pattern)):
        intervals.append(stress_pattern[i] - stress_pattern[i-1])
    
    interval_patterns = {
        'ямб': 2,
        'хорей': 2,
        'дактиль': 3,
        'амфибрахий': 3,
        'анапест': 3
    }
    
    if intervals:
        avg_interval = sum(intervals) / len(intervals)
        
        if 2.6 <= avg_interval <= 3.4:
            if stress_pattern[0] % 3 == 0:
                meter_scores['дактиль'] += 20
            elif stress_pattern[0] % 3 == 1:
                meter_scores['амфибрахий'] += 20
            elif stress_pattern[0] % 3 == 2 or stress_pattern[0] % 3 == -1:
                meter_scores['анапест'] += 20
        elif 1.6 <= avg_interval <= 2.4:
            if all(pos % 2 == 0 for pos in stress_pattern) or all(pos % 2 == 1 for pos in stress_pattern):
                if stress_pattern[0] % 2 == 1:
                    meter_scores['хорей'] += 15
                else:
                    meter_scores['ямб'] += 15
    
    best_meter = max(meter_scores.items(), key=lambda x: x[1])
    
    return best_meter[0]

def analyze_rhythm(stress_pattern):
    if not stress_pattern:
        return {
            "rhythm_type": "неопределенный",
            "stress_density": 0,
            "stress_intervals": []
        }
    
    total_syllables = max(stress_pattern) + 1 if stress_pattern else 0
    stress_count = len(stress_pattern)
    stress_density = stress_count / total_syllables if total_syllables > 0 else 0
    
    stress_intervals = []
    for i in range(1, len(stress_pattern)):
        interval = stress_pattern[i] - stress_pattern[i-1]
        stress_intervals.append(interval)
    
    rhythm_type = "неопределенный"
    if stress_intervals:
        avg_interval = sum(stress_intervals) / len(stress_intervals)
        if 1.8 <= avg_interval <= 2.2:
            rhythm_type = "двусложный"
        elif 2.8 <= avg_interval <= 3.2:
            rhythm_type = "трехсложный"
    
    return {
        "rhythm_type": rhythm_type,
        "stress_density": stress_density,
        "stress_intervals": stress_intervals
    }

def load_ruaccent_model():
    try:
        from ruaccent import RUAccent
        
        try:
            accentizer = RUAccent(
                omograph_model_size='tiny',
                use_dictionary=True,
                tiny_mode=True
            )
           
            return accentizer
        except TypeError as e:
            try:
                accentizer = RUAccent()
                accentizer.load(omograph_model_size='tiny', use_dictionary=True, tiny_mode=True)
                return accentizer
            except Exception as e2:
                print(f"Ошибка при загрузке модели вторым способом: {e2}")
                return None
        except Exception as e:
            print(f"Ошибка при загрузке модели RUAccent: {e}")
            print(f"Тип ошибки: {type(e).__name__}")
            print("Проверьте версию библиотеки RUAccent и Python")
            return None
    except ImportError:
        print("Библиотека не установлена. Для работы программы необходимо установить библиотеку:")
        return None

def count_syllables_en(word):

    word = clean_word(word)
    if not word:
        return 0
        
    vowels = 'aeiouy'
    
    exceptions = {
        'e': 1, 'a': 1, 'i': 1, 'o': 1, 'u': 1, 'y': 1,
        'the': 1, 'was': 1, 'were': 1, 'an': 1, 'for': 1, 'to': 1, 'in': 1, 'on': 1,
        'and': 1, 'but': 1, 'or': 1, 'from': 1, 'of': 1
    }
    
    if word.lower() in exceptions:
        return exceptions[word.lower()]
    
    count = 0
    prev_is_vowel = False
    
    word_for_count = word.lower()
    if word_for_count.endswith('e') and len(word_for_count) > 2:
        word_for_count = word_for_count[:-1]
    
    for char in word_for_count:
        is_vowel = char.lower() in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel
    
    if count == 0:
        count = 1
    
    return count

def detect_syllables_en(text):
    words = text.split()
    count = 0
    
    for word in words:
        count += count_syllables_en(word)
    
    return count

def detect_stress_pattern_en(line, stress_dict=None):
    if not line.strip():
        return []
    
    if stress_dict is None:
        stress_dict = load_stress_dict(language='en')
    
    line = line.lower()
    line = clean_text(line)
    words = line.split()
    
    pattern = []
    syllable_count = 0
    
    for word in words:
        clean_w = clean_word(word)
        if not clean_w:
            continue
            
        word_stress = find_word_stress_pattern(clean_w, language='en', stress_dict=stress_dict)
        
        for stress_pos in word_stress:
            pattern.append(syllable_count + stress_pos)
            
        syllable_count += count_syllables_en(clean_w)
    
    return pattern

def identify_meter_en(stress_pattern):
    if not stress_pattern or len(stress_pattern) < 2:
        return "undefined meter", {}
    
    stresses = stress_pattern
    
    if not stresses:
        return "undefined meter", {}
    
    patterns = {
        'iamb': lambda x: x % 2 == 1,
        'trochee': lambda x: x % 2 == 0,
        'dactyl': lambda x: x % 3 == 0,
        'amphibrach': lambda x: x % 3 == 1,
        'anapest': lambda x: x % 3 == 2
    }
    
    scores = {}
    for name, check in patterns.items():
        matches = sum(1 for pos in stresses if check(pos))
        scores[name] = matches / len(stresses) * 100
    
    two_syllable_score = max(scores['iamb'], scores['trochee'])
    three_syllable_score = max(scores['dactyl'], scores['amphibrach'], scores['anapest'])
    
    if two_syllable_score >= three_syllable_score:
        best = max(['iamb', 'trochee'], key=lambda x: scores[x])
    else:
        best = max(['dactyl', 'amphibrach', 'anapest'], key=lambda x: scores[x])
    
    meter_translation = {
        'iamb': 'ямб',
        'trochee': 'хорей',
        'dactyl': 'дактиль',
        'amphibrach': 'амфибрахий',
        'anapest': 'анапест'
    }
    
    
    return meter_translation[best], scores

def analyze_english_poem(text):
    stress_dict = load_stress_dict(language='en')
    
    lines = text.strip().split('\n')
    
    results = []
    all_stress_patterns = []
    
    for i, line in enumerate(lines):
        clean_line = clean_text(line)
        if not clean_line.strip():
            continue
            
        stress_pattern = detect_stress_pattern_en(clean_line, stress_dict)
        all_stress_patterns.extend(stress_pattern)
        
        meter, scores = identify_meter_en(stress_pattern)
        
        rhythm_info = analyze_rhythm(stress_pattern)
        
        results.append({
            'line': line,
            'stress_pattern': stress_pattern,
            'meter': meter,
            'rhythm_info': rhythm_info,
            'scores': scores
        })
    
    overall_meter, overall_scores = identify_meter_en(all_stress_patterns)
    
    return {
        'lines_analysis': results,
        'overall_meter': overall_meter,
        'overall_scores': overall_scores
    }

def find_word_stress_pattern(word, language='ru', stress_dict=None):
    word = clean_word(word)
    if not word:
        return []
    
    if stress_dict is None:
        stress_dict = load_stress_dict(language=language)
    
    if word.lower() in stress_dict:
        return stress_dict[word.lower()]
    
    if language == 'en':
        syllables = count_syllables_en(word)
        
        if syllables == 1:
            return [0]
        elif syllables == 2:
            return [0]
        else:
            return [0 if len(word) < 7 else 1]
    
    return [] 

def load_stress_dict(language='ru'):

    try:
        dict_path = ""
        if language == 'ru':
            dict_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'dictionaries', 'stress_dict_ru.json')
        elif language == 'en':
            dict_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'dictionaries', 'stress_dict_en.json')
        else:
            print(f"Неподдерживаемый язык: {language}")
            return {}
            
        if not os.path.exists(dict_path):
            print(f"Словарь ударений для языка {language} не найден по пути: {dict_path}")
            return {}
            
        with open(dict_path, 'r', encoding='utf-8') as f:
            stress_dict = json.load(f)
            
        print(f"Словарь ударений для языка {language} загружен ({len(stress_dict)} слов)")
        return stress_dict
    except Exception as e:
        print(f"Ошибка при загрузке словаря ударений: {e}")
        return {}

 