import logging
from pathlib import Path
import json 
from collections import Counter
import sys
import os
import time

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("Библиотека python-dotenv не установлена. API ключ нужно будет передавать иным способом или он не будет загружен.")

try:
    import google.generativeai as genai
    GEMINI_API_AVAILABLE = True
except ImportError:
    GEMINI_API_AVAILABLE = False
    print("Библиотека google-generativeai не установлена. Автоматический перевод через Gemini API будет недоступен.")


script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
meter_detector_path = project_root / "poetry_meter_detector"
if str(meter_detector_path) not in sys.path:
    sys.path.append(str(meter_detector_path))

try:
    from utils import preprocess
except ImportError as e:
    print(f"Ошибка импорта preprocess: {e}")
    print(f"Sys.path: {sys.path}")

    try:
        import poetry_meter_detector.utils.preprocess as preprocess
        print("Успешно импортирован poetry_meter_detector.utils.preprocess")
    except ImportError:
        print("Не удалось импортировать preprocess. Убедитесь, что poetry_meter_detector доступен.")
        sys.exit(1)


def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = logging.FileHandler('translation_analysis.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

logger = setup_logger()


def get_translation_via_gemini_api(prompt_text: str, api_key: str) -> str | None:
    if not GEMINI_API_AVAILABLE:
        logger.warning("Библиотека google-generativeai недоступна. Пропуск вызова API.")
        return None
    if not api_key:
        logger.warning("API ключ для Gemini не предоставлен. Пропуск вызова API.")
        return None

    logger.info("Попытка получить перевод через Gemini API...")
    try:
        genai.configure(api_key=api_key)
        model_name = 'models/gemini-1.5-flash-latest'
        logger.info(f"Используемая модель Gemini: {model_name}")
        model = genai.GenerativeModel(model_name)
        requested_temperature = 2.0
        logger.info(f"Запрошенная температура: {requested_temperature}")

        generation_config = genai.types.GenerationConfig(
            temperature=requested_temperature, 
            max_output_tokens=2048
        )

        logger.info(f"Параметры генерации для API: {generation_config}")

        response = model.generate_content(
            prompt_text,
            generation_config=generation_config
        )
        
        if response.parts:
            translation = response.text
            logger.info("Перевод успешно получен от Gemini API.")
            return translation
        else:
            logger.warning("Gemini API вернул пустой ответ (no parts). Возможно, сработали фильтры безопасности или другая проблема.")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                 logger.warning(f"Prompt Feedback: {response.prompt_feedback}")
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'finish_reason') and candidate.finish_reason != 'STOP':
                        logger.warning(f"Кандидат завершился с причиной: {candidate.finish_reason}")
                        if hasattr(candidate, 'safety_ratings'):
                            logger.warning(f"  Safety Ratings: {candidate.safety_ratings}")
            return None

    except Exception as e:
        logger.error(f"Ошибка при вызове Gemini API: {e}", exc_info=True)
        if "Unsupported parameter" in str(e) or "Invalid value" in str(e):
            logger.error("Возможно, указанная температура или другие параметры не поддерживаются для этой модели/версии API.")
        elif "Could not find model" in str(e) or "is not found" in str(e):
            logger.error(f"Модель '{model_name}' не найдена. Проверьте правильность имени и доступность для вашего API ключа.")
        elif "billing account" in str(e).lower() or "quota" in str(e).lower() or "resourceexhausted" in str(e).lower():
            logger.error(f"Проблема с квотами или биллингом для модели '{model_name}'. Эта модель может не иметь бесплатного уровня или вы исчерпали лимиты.")
        return None

def process_poem_and_translate(input_file: str, output_file: str, prompt_file: str):
    gemini_api_key = None
    if DOTENV_AVAILABLE:
        load_dotenv()
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            logger.info("API ключ GEMINI_API_KEY загружен из .env файла.")
        else:
            logger.warning("Переменная GEMINI_API_KEY не найдена в .env файле.")
    else:
        logger.warning("Библиотека python-dotenv недоступна, API ключ не будет загружен автоматически из .env.")

    try:
        logger.info(f"Начинаем анализ стихотворения из файла '{input_file}' для подготовки промпта GPT...")

        input_file_path = Path(input_file)
        if not input_file_path.exists():
            logger.error(f"Файл не найден: {input_file_path}")
            print(f"Ошибка: Входной файл '{input_file}' не найден.")
            return
            
        with open(input_file_path, "r", encoding="utf-8") as f:
            original_text = f.read()
        logger.info("Входной файл успешно прочитан.")

        logger.info("Загрузка модели для анализа ударений...")
        accentizer = preprocess.load_ruaccent_model()
        
        if not accentizer:
            logger.error("Не удалось загрузить модель. Анализ метра и ритма невозможен.")
            error_message = "Ошибка: Не удалось загрузить модель. Проверьте лог 'translation_analysis.log'."
            with open(output_file, "w", encoding="utf-8") as f_out:
                f_out.write(error_message)
            print(error_message)
            return
        logger.info("Модель успешно загружена.")

        lines = preprocess.split_into_lines(original_text)
        if not lines:
            logger.warning("Входной текст не содержит строк для анализа после разделения.")
            with open(output_file, "w", encoding="utf-8") as f_out:
                f_out.write("Входной файл не содержит текста для анализа или текст не удалось разделить на строки.")
            return

        logger.info(f"Текст разделен на {len(lines)} строк для анализа.")
        
        line_analysis_details = []
        all_meters = []

        for i, line_text in enumerate(lines):
            if not line_text.strip():
                continue
            
            logger.debug(f'Анализ строки {i+1}: "{line_text}"')
            stress_pattern = preprocess.detect_stress_pattern(line_text, accentizer=accentizer, language='ru')
            meter = "неопределенный размер"
            rhythm_info = {"rhythm_type": "неопределенный", "stress_density": 0, "stress_intervals": []}

            if stress_pattern:
                meter = preprocess.identify_meter(stress_pattern)
                rhythm_info = preprocess.analyze_rhythm(stress_pattern)
                if meter != "неопределенный размер":
                    all_meters.append(meter)
            
            line_analysis_details.append({
                "line_number": i + 1,
                "text": line_text,
                "stress_pattern": stress_pattern,
                "meter": meter,
                "rhythm_type": rhythm_info['rhythm_type'],
                "stress_density": rhythm_info['stress_density'],
                "stress_intervals": rhythm_info['stress_intervals']
            })
            logger.debug(f"Строка {i+1} анализ: метр={meter}, ритм={rhythm_info['rhythm_type']}")

        dominant_meter = "Не удалось определить"
        if all_meters:
            meter_counts = Counter(all_meters)
            dominant_meter = meter_counts.most_common(1)[0][0]
        logger.info(f"Доминирующий метр (если есть): {dominant_meter}")

        analysis_summary_parts = [f"Общий доминирующий метр: {dominant_meter}"]
        for detail in line_analysis_details:
            analysis_summary_parts.append(
                f"Строка {detail['line_number']}: \"{detail['text']}\"\n"
                f"  - Ударения (позиции слогов): {detail['stress_pattern']}\n"
                f"  - Метр: {detail['meter']}\n"
                f"  - Тип ритма: {detail['rhythm_type']}\n"
                f"  - Плотность ударений: {detail['stress_density']:.2f}\n"
                f"  - Интервалы между ударениями: {detail['stress_intervals']}"
            )
        full_analysis_text = "\n".join(analysis_summary_parts)
        
        logger.info("Анализ стихотворения завершен.")

        prompt_text = f"""Тебе будет дано стихотворение на русском языке и подробный анализ его стихотворного размера (метра) и ритма.
Твоя задача — выполнить высококачественный художественный перевод этого стихотворения на английский язык.

Ключевые требования к переводу:
1.  **Сохранение смысла**: Точно передать оригинальное сообщение, эмоции и образы стихотворения.
2.  **Соблюдение стихотворного размера и ритма**: Постарайся максимально приблизить английский перевод к метру и ритму оригинала. Используй предоставленный анализ как ориентир. Если точное соответствие невозможно, стремись к гармоничному поэтическому звучанию на английском.
3.  **ОБЯЗАТЕЛЬНОЕ НАЛИЧIE РИФМЫ**: Перевод должен быть рифмованным. Рифма должна быть естественной, осмысленной и благозвучной в английском языке. Избегай примитивных или натянутых рифм.
4.  **Поэтичность и стиль**: Перевод должен звучать как настоящее стихотворение на английском, а не как дословный или технический пересказ. Сохрани, по возможности, стиль и тон оригинала.
5.  **Целостность**: Переведи все строки и строфы стихотворения.

Оригинальное стихотворение (Русский):
---
{original_text}
---

Подробный анализ оригинального стихотворения:
---
{full_analysis_text}
---

Пожалуйста, предоставь ТОЛЬКО английский перевод стихотворения, без дополнительных комментариев или пояснений с твоей стороны.

Английский перевод:
"""
        logger.info("Промпт для GPT успешно сформирован.")

        prompt_file_path = Path(prompt_file)
        with open(prompt_file_path, "w", encoding="utf-8") as f_prompt:
            f_prompt.write(prompt_text)
        logger.info(f"Промпт сохранен в файл: {prompt_file_path.absolute()} (на случай, если API не сработает или для справки)")

        api_translation = None
        if gemini_api_key and GEMINI_API_AVAILABLE:
            api_translation = get_translation_via_gemini_api(prompt_text, gemini_api_key)
        
        output_file_path = Path(output_file)
        if api_translation:
            with open(output_file_path, "w", encoding="utf-8") as f_out:
                f_out.write(api_translation)
            logger.info(f"Перевод через Gemini API успешно сохранен в: {output_file_path.absolute()}")
            print(f"Анализ и автоматический перевод завершены. Результат в '{output_file_path.absolute()}'.")
        else:
            logger.warning("Автоматический перевод через Gemini API не удался или был пропущен.")
            user_instructions = f"""Скрипт успешно проанализировал русское стихотворение из '{input_file}'
и сгенерировал подробный промпт для его перевода.

Промпт сохранен в файле:
{prompt_file_path.absolute()}

Автоматический перевод через Gemini API не удался или был пропущен.
Что делать дальше для ручного перевода:
1.  Откройте файл '{prompt_file_path.name}'.
2.  Скопируйте ВСЁ его содержимое.
3.  Вставьте скопированный текст в интерфейс мощной языковой модели (например, ChatGPT, Google Gemini web UI, Claude и т.д.).
4.  Получите от модели английский перевод.
5.  Вставьте полученный английский перевод в ЭТОТ файл ({output_file_path.name}), заменив данный текст.

Удачи с переводом!
"""
            with open(output_file_path, "w", encoding="utf-8") as f_out:
                f_out.write(user_instructions)
            logger.info(f"Инструкции для ручного перевода сохранены в: {output_file_path.absolute()}")
            print(f"Анализ завершен. Промпт для GPT/Gemini сохранен в '{prompt_file_path.absolute()}'.")
            print(f"Инструкции по дальнейшим действиям (ручной перевод) находятся в файле '{output_file_path.absolute()}'.")

    except ImportError:
        logger.critical("Критическая ошибка: не удалось импортировать модуль preprocess. Скрипт не может продолжить работу.")
        print("Критическая ошибка: не удалось импортировать модуль preprocess. Проверьте пути и доступность модуля.")
    except Exception as e:
        error_msg = f"Произошла ошибка: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(error_msg)
        try:
            with open(output_file, "w", encoding="utf-8") as f_out:
                f_out.write(f"Произошла критическая ошибка во время выполнения скрипта:\n{error_msg}\n\nПожалуйста, проверьте лог-файл 'translation_analysis.log' для получения подробной информации.")
        except Exception as e_write:
            logger.error(f"Не удалось даже записать сообщение об ошибке в output_file: {e_write}")
        raise

if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    
    input_filename = base_dir / "input_file.txt"
    output_filename = base_dir / "output_file.txt"
    gpt_prompt_filename = base_dir / "gpt_prompt.txt"

    if 'preprocess' not in globals() or not callable(getattr(preprocess, 'load_ruaccent_model', None)):
        logger.critical("Модуль preprocess не был корректно загружен. Выполнение прервано.")
        print("Ошибка: Модуль preprocess не загружен. Проверьте импорты и пути.")
    else:
        process_poem_and_translate(str(input_filename), str(output_filename), str(gpt_prompt_filename)) 