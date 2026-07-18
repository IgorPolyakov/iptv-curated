#!/usr/bin/env python3
"""
Курация upstream MEGA IPTV-плейлиста:
- фильтр RU + мировые топ, без иностранного/взрослого
- группировка по жанрам, популярные федеральные вверху
- дедупликация (макс 2 источника на канал), чистка битых логотипов
"""
import re, os, unicodedata, urllib.request

SRC_URL = os.environ.get("UPSTREAM_URL",
    "https://raw.githubusercontent.com/IPTVRU2026/IPTVMIR/main/IPTV_MEGA_PLAYLIST.m3u")
OUT = os.environ.get("OUT", "curated.m3u")

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", errors="replace")

def read_pairs(text):
    lines = text.splitlines()
    pairs = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#EXTINF"):
            url = None; j = i + 1; extra = []
            while j < len(lines):
                nxt = lines[j]
                if nxt.startswith("#EXTINF"):
                    break
                if nxt.strip() and not nxt.startswith("#"):
                    url = nxt.strip(); j += 1; break
                if nxt.startswith("#") and nxt.strip():
                    extra.append(nxt)
                j += 1
            if url:
                pairs.append((ln, extra, url))
            i = j
        else:
            i += 1
    return pairs

def get_group(ext):
    m = re.search(r'group-title="([^"]*)"', ext)
    return m.group(1) if m else ""

def get_name(ext):
    return ext.rsplit(",", 1)[-1].strip()

def norm(name):
    s = name.lower()
    s = re.sub(r'\(.*?\)', ' ', s)
    s = re.sub(r'\[.*?\]', ' ', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'\b(hd|fhd|uhd|4k|sd|720p|1080p|576p|360p|480p|backup|vpn)\b', ' ', s)
    s = re.sub(r'[^0-9a-zа-яё ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

CYR = re.compile(r'[А-Яа-яЁё]')
ADULT = ['эротик','adult','18+','xxx','erotic','playboy','brazzers','big dick','sex','порн']
INTL = ['discovery','national geographic','nat geo','animal planet','euronews','bbc',
        'cnn ','eurosport','cartoon network','nickelodeon','nick jr','disney','mtv',
        'history','viasat','tlc','da vinci','love nature','fashion tv','fashiontv',
        'travel channel','dw ','france 24','paramount','sony channel','fox ','hbo',
        'cinemax','food network','deutsche welle','rt ','russia today','red bull tv']
FOREIGN_GROUP = ['иран','арабск','италия','германия','испания','турци','азер','грузи',
                 'армени','франц','польш','румын','болгар','сербск','греч','португал',
                 'китай','корея','япони','индия','вьетнам','таиланд','бразил','мексик',
                 'нидерланд','чехия','венгр','швеци','норвег','финлянд']

def classify(name, group):
    blob = name.lower() + " " + group.lower()
    def has(*ws): return any(w in blob for w in ws)
    if has('матч','match tv','футбол','спорт','sport','eurosport','кхл','хоккей','бокс','ufc'):
        return 'Спорт'
    if has('новост','россия 24','рбк','euronews','cnn','bbc world','известия','мир 24','вести'):
        return 'Новости'
    if has('карусел','мульт','детск','cartoon','nick','disney','малыш','tiji','baby','gulli','kids'):
        return 'Детские'
    if has('discovery','national geographic','nat geo','history','наук','познават','da vinci','animal','знание','рыбалк','охот'):
        return 'Познавательные'
    if has('муз','music','mtv','shanson','шансон','ru.tv','bridge','europa plus','радио'):
        return 'Музыка'
    if has('кино','film','cinema','фильм','tv1000','дом кино','cineram','премьер','viju','иллюзион'):
        return 'Фильмы'
    if has('сериал','домашний'):
        return 'Сериалы'
    return None

POPULAR = ['первый канал','россия 1','россия 24','нтв','тнт','стс','пятый канал','рен',
           'тв центр','тв-3','домашний','звезда','пятница','че','2х2','карусель',
           'матч тв','россия к','муз-тв','спас','отр']

def pop_rank(name):
    nn = norm(name)
    for i, p in enumerate(POPULAR):
        if nn.startswith(norm(p)) or norm(p) in nn:
            return i
    return len(POPULAR) + 1

def main():
    text = fetch(SRC_URL)
    pairs = read_pairs(text)
    order = ['Эфирные','Новости','Фильмы','Сериалы','Спорт','Познавательные','Детские','Музыка','Региональные','Прочее RU']
    buckets = {b: [] for b in order}
    seen = {}; MAXDUP = 2
    for ext, extra, url in pairs:
        name = get_name(ext); group = get_group(ext)
        if not name:
            continue
        blob = (name + " " + group).lower()
        if any(a in blob for a in ADULT):
            continue
        is_ru = bool(CYR.search(name)) or bool(CYR.search(group)) or 'россия' in group.lower() or '.ru' in blob
        is_intl = any(w in (name.lower() + " ") for w in INTL)
        if any(f in group.lower() for f in FOREIGN_GROUP) and not is_intl:
            continue
        if not is_ru and not is_intl:
            continue
        key = norm(name)
        if not key:
            continue
        if seen.get(key, 0) >= MAXDUP:
            continue
        seen[key] = seen.get(key, 0) + 1
        genre = classify(name, group)
        is_regional = ('zabava' in group.lower()) or ('регион' in group.lower()) or bool(re.search(r'\((?:[А-Яа-яё .-]+обл|[А-Яа-яё .-]+край)\)', name, re.I))
        if genre is None:
            if is_ru and is_regional:
                bucket = 'Региональные'
            elif is_ru and pop_rank(name) <= len(POPULAR):
                bucket = 'Эфирные'
            elif is_ru:
                bucket = 'Прочее RU'
            else:
                bucket = 'Познавательные'
        else:
            bucket = genre
        clean_ext = '#EXTINF:-1 group-title="%s",%s' % (bucket, name)
        buckets[bucket].append((pop_rank(name), name.lower(), clean_ext, extra, url))
    total = 0
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for b in order:
            for _, _, ext, extra, url in sorted(buckets[b], key=lambda x: (x[0], x[1])):
                f.write(ext + "\n")
                for e in extra:
                    f.write(e + "\n")
                f.write(url + "\n")
                total += 1
    print("channels: %d" % total)
    for b in order:
        print("  %5d  %s" % (len(buckets[b]), b))

if __name__ == "__main__":
    main()
