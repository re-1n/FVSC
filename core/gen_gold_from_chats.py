# -*- coding: utf-8 -*-
"""
Генератор gold_extended из Davur+Key7 чатов с полным контекстом.

Формат: (sentence, context, judgments, meta_type)
  sentence — целевое предложение
  context — список предыдущих сообщений для разрешения анафор
  judgments — S→V→O суждения
  meta_type — тип метапропозиции
"""

import json
from datetime import datetime

def load_chats():
    """Загружает оба экспорта"""
    chats = []
    
    # Первый экспорт
    with open('../другое/экспорты чатов/result (Davurr and key7).json', 'r', encoding='utf-8') as f:
        data1 = json.load(f)
        chats.append(data1)
    
    # Второй экспорт
    with open('../другое/экспорты чатов/result Davur Key7 2.json', 'r', encoding='utf-8') as f:
        data2 = json.load(f)
        chats.append(data2)
    
    return chats

def extract_text(msg):
    """Извлекает текст из сообщения"""
    if 'text' in msg and msg['text']:
        return msg['text']
    return None

def build_discourse_units(chats):
    """Строит discourse units с контекстом"""
    
    # Собираем все сообщения с датой
    all_messages = []
    for chat in chats:
        for msg in chat.get('messages', []):
            if msg.get('type') == 'message':
                text = extract_text(msg)
                if text:
                    try:
                        date = datetime.fromisoformat(msg['date'].replace('Z', '+00:00'))
                    except:
                        date = datetime.now()
                    
                    from_user = msg.get('from', 'Unknown')
                    all_messages.append({
                        'text': text,
                        'date': date,
                        'from': from_user
                    })
    
    # Сортируем по дате
    all_messages.sort(key=lambda x: x['date'])
    
    print(f"✓ Загружено {len(all_messages)} сообщений")
    
    # Строим discourse units (sentence + context)
    units = []
    for i, msg in enumerate(all_messages):
        # Контекст: 2 предыдущих сообщения
        context = []
        if i > 0:
            context.append(all_messages[i-1]['text'])
        if i > 1:
            context.append(all_messages[i-2]['text'])
        
        units.append({
            'sentence': msg['text'],
            'context': context,
            'from': msg['from']
        })
    
    return units

def generate_gold_extended_code(units):
    """Генерирует Python код для gold_extended.py"""
    
    code = """# -*- coding: utf-8 -*-
\"\"\"
Расширенный eval set из Davur+Key7 чатов с полным контекстом.

ФОРМАТ: (sentence, context, judgments, meta_type)
  sentence — целевое предложение
  context — список предыдущих сообщений (для разрешения анафор)
  judgments — S→V→O суждения
  meta_type — тип метапропозиции

Контекст помогает разрешить анафорические ссылки (это, один, как и, тот, который).

META_TYPE:
  None — обычное суждение
  "generalization" — обобщение предыдущего контекста
  "classification" — классификация явления
  "similarity" — связь через общий атрибут
  "interpretation" — интерпретация
  "reference" — прямая ссылка на предыдущее
\"\"\"

GOLD_EXTENDED = [
"""
    
    for i, unit in enumerate(units[:100]):  # Первые 100
        sentence = unit['sentence'].replace('"', '\\"')
        context = unit['context']
        context_repr = repr(context)
        
        code += f"    # [{i}] {unit['from']}\n"
        code += f"    ({repr(sentence)}, {context_repr}, [], None),\n"
        code += "\n"
    
    code += "]\n"
    
    return code

if __name__ == '__main__':
    print("📥 Загружаю чаты...")
    chats = load_chats()
    
    print("🔨 Строю discourse units...")
    units = build_discourse_units(chats)
    
    print(f"✓ Построено {len(units)} units")
    
    # Показываем примеры
    print("\n📋 Примеры:")
    for i in range(min(3, len(units))):
        print(f"\n[{i}] Sentence: {units[i]['sentence'][:60]}...")
        if units[i]['context']:
            print(f"    Context: {units[i]['context'][0][:60]}...")
    
    print("\n💾 Генерирую gold_extended.py...")
    code = generate_gold_extended_code(units)
    
    with open('gold_extended_davur_key7.py', 'w', encoding='utf-8') as f:
        f.write(code)
    
    print("✓ Сохранено в gold_extended_davur_key7.py")
