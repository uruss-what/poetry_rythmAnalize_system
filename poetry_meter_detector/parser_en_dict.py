import json
import re

input_path = "poetry_meter_detector/cmudict-0.7b"
output_path = "poetry_meter_detector/data/dictionaries/stress_dict_en.json"

stress_dict = {}

with open(input_path, "r", encoding="latin-1") as f:
    for line in f:
        if line.startswith(";;;"):
            continue

        parts = line.strip().split()
        if not parts:
            continue

        word = parts[0]
        phonemes = parts[1:]

        word = re.sub(r"\(\d+\)", "", word).lower()

        stress_pattern = []
        for phoneme in phonemes:
            match = re.search(r"[012]", phoneme)
            if match:
                stress = int(match.group())
                stress_pattern.append(0 if stress == 2 else stress)

        if word not in stress_dict:
            stress_dict[word] = stress_pattern

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(stress_dict, f, indent=2, ensure_ascii=False)
