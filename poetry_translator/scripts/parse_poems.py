import requests
from bs4 import BeautifulSoup
import re
import os
from pathlib import Path
import time

def clean_poem_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    lines = re.split(r'[.!?]', text)
    lines = [line.strip() for line in lines if line.strip()]
    return '\n'.join(lines)

def get_soup(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')

def is_author_link(a):
    href = a.get('href', '')
    return href and not href.startswith('http') and not href.startswith('#') and '/site/poetryandtranslations/' in href and 'homepage1' not in href

def is_poem_link(href, author_slug):
    if not href.startswith('/site/poetryandtranslations/'):
        return False
    if href.rstrip('/').endswith(author_slug):
        return False
    for bad in ['manifesto', 'biography', 'books', 'youtube', 'contact', 'home', 'various', 'my-books', 'on-youtube']:
        if bad in href:
            return False
    if href.startswith('#') or href.startswith('http'):
        return False
    return True

def extract_russian_poem_from_page(url):
    soup = get_soup(url)
    
    ru_paragraphs = []
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if text and re.search(r'[а-яА-ЯёЁ]', text):
            if not any(x in text.lower() for x in ['home', 'manifesto', 'biography', 'books', 'contact']):
                ru_paragraphs.append(text)
    
    if not ru_paragraphs:
        return ''
    
    poem = '\n'.join(ru_paragraphs)
    return clean_poem_text(poem)

def extract_english_poem_from_page(url):
    soup = get_soup(url)
    
    en_paragraphs = []
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if text and not re.search(r'[а-яА-ЯёЁ]', text):
            if not any(x in text.lower() for x in ['home', 'manifesto', 'biography', 'books', 'contact']):
                en_paragraphs.append(text)
    
    if not en_paragraphs:
        return ''
    
    poem = '\n'.join(en_paragraphs)
    return clean_poem_text(poem)

def get_poem_links_from_author_page(url):
    soup = get_soup(url)
    poem_links = []
    author_slug = url.rstrip('/').split('/')[-1]
    
    for a in soup.find_all('a'):
        href = a.get('href', '')
        text = a.get_text(strip=True)
        if is_poem_link(href, author_slug):
            if href.startswith('/site/poetryandtranslations/'):
                href = href.replace('/site/poetryandtranslations/', '')
            full_url = 'https://sites.google.com/site/poetryandtranslations/' + href
            poem_links.append(full_url)
            print(f'Добавлена ссылка на стихотворение: {text} -> {full_url}')
    return list(set(poem_links))

def main():
    base = 'https://sites.google.com/site/poetryandtranslations/'
    homepage = 'https://sites.google.com/site/poetryandtranslations/homepage1'
    data_dir = Path('poetry_translator/data/raw')
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print('Парсим главную страницу...')
    soup = get_soup(homepage)
    author_links = []
    for a in soup.find_all('a'):
        if is_author_link(a):
            href = a['href']
            if href.startswith('/site/poetryandtranslations/'):
                href = href.replace('/site/poetryandtranslations/', '')
            if not href.startswith('http'):
                href = base + href
            author_links.append(href)
    author_links = list(set(author_links))
    print(f'Найдено авторов: {len(author_links)}')
    
    poem_links = set()
    for author_url in author_links:
        try:
            print(f'Парсим страницу автора: {author_url}')
            author_poem_links = get_poem_links_from_author_page(author_url)
            print(f'Найдено стихотворений у автора: {len(author_poem_links)}')
            poem_links.update(author_poem_links)
            time.sleep(1)
        except Exception as e:
            print(f'Ошибка при парсинге автора: {e}')
    
    poem_links = list(poem_links)
    print(f'Всего найдено стихотворений: {len(poem_links)}')
    
    ru_poems = []
    en_poems = []
    for i, poem_url in enumerate(poem_links):
        try:
            print(f'[{i+1}/{len(poem_links)}] Парсим стихотворение: {poem_url}')
            
            ru_poem = extract_russian_poem_from_page(poem_url)
            en_poem = extract_english_poem_from_page(poem_url)
            
            if ru_poem and en_poem:
                ru_poems.append(ru_poem)
                en_poems.append(en_poem)
                print(f'Успешно извлечены русский и английский варианты')
                print(f'Русский текст: {ru_poem[:100]}...')
                print(f'Английский текст: {en_poem[:100]}...')
            else:
                print(f'Не удалось извлечь оба варианта текста')
            time.sleep(1)
        except Exception as e:
            print(f'Ошибка при парсинге стихотворения: {e}')
    
    print(f'Всего собрано пар стихотворений: {len(ru_poems)}')
    
    if not ru_poems or not en_poems:
        print('Внимание: один из списков стихов пуст!')
    else:
        print(f'Сохранение результатов...')
        with open(data_dir / 'source_poems.txt', 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(ru_poems))
        with open(data_dir / 'target_poems.txt', 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(en_poems))
        print(f'Сохранено пар стихотворений: {len(ru_poems)}')
        
        print('\nПроверка содержимого файлов:')
        with open(data_dir / 'source_poems.txt', 'r', encoding='utf-8') as f:
            source_content = f.read()
            print(f'Размер source_poems.txt: {len(source_content)} байт')
            print(f'Первые 200 символов: {source_content[:200]}')
        
        with open(data_dir / 'target_poems.txt', 'r', encoding='utf-8') as f:
            target_content = f.read()
            print(f'Размер target_poems.txt: {len(target_content)} байт')
            print(f'Первые 200 символов: {target_content[:200]}')

if __name__ == '__main__':
    main() 