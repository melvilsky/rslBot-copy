"""
Тестовый скрипт для проверки claim_refill в Live Arena
Работает со скриншотами из папки tests/screenshots/

Использование:
1. Сделайте скриншот экрана Live Arena
2. Сохраните его в tests/screenshots/ (например, live_arena_screenshot.png)
3. Запустите скрипт: python tests/test_live_arena_claim_refill.py
4. Укажите имя файла скриншота при запросе
"""

import os
import sys

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠️  Pillow (PIL) не установлен. Установите: pip install Pillow")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("⚠️  NumPy не установлен. Установите: pip install numpy")

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Локальная копия функции rgb_check (чтобы не зависеть от helpers.common)
def rgb_check(rgb_1, rgb_2, mistake=0):
    """Проверяет, совпадают ли два RGB цвета с учетом допуска"""
    if all(abs(rgb_1[i] - rgb_2[i]) <= mistake for i in range(3)):
        return True
    return False


def load_screenshot(filepath):
    """Загружает скриншот из файла"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Скриншот не найден: {filepath}")
    
    if not HAS_PIL:
        raise ImportError("Pillow (PIL) необходим для работы со скриншотами")
    
    img = Image.open(filepath)
    img_rgb = img.convert('RGB')
    
    # Конвертируем в numpy array для работы с пикселями
    if HAS_NUMPY:
        img_array = np.array(img_rgb)
    else:
        img_array = img_rgb
    
    return img_array, (img.height, img.width, 3)


def check_pixel_on_image(img, x, y, expected_rgb, mistake=10):
    """Проверяет цвет пикселя на изображении"""
    if HAS_NUMPY:
        if x >= img.shape[1] or y >= img.shape[0] or x < 0 or y < 0:
            return False, None, None
        actual_rgb = [int(img[y, x, 0]), int(img[y, x, 1]), int(img[y, x, 2])]
    else:
        # Используем PIL напрямую
        if x >= img.width or y >= img.height or x < 0 or y < 0:
            return False, None, None
        pixel = img.getpixel((x, y))
        actual_rgb = list(pixel) if isinstance(pixel, tuple) else [pixel, pixel, pixel]
    
    matches = rgb_check(actual_rgb, expected_rgb, mistake=mistake)
    
    diff = [abs(actual_rgb[i] - expected_rgb[i]) for i in range(3)]
    max_diff = max(diff)
    
    return matches, actual_rgb, max_diff


def find_red_dots_in_region(img, region, target_rgb=[218, 0, 0], mistake=30):
    """Находит все красные точки в указанной области"""
    x1, y1, width, height = region
    x2 = x1 + width
    y2 = y1 + height
    
    # Ограничиваем область размерами изображения
    if HAS_NUMPY:
        max_x, max_y = img.shape[1], img.shape[0]
    else:
        max_x, max_y = img.width, img.height
    
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(max_x, x2)
    y2 = min(max_y, y2)
    
    red_dots = []
    
    # Оптимизация: проверяем каждый пиксель (убрали step для более точного поиска)
    step = 1
    
    for y in range(y1, y2, step):
        for x in range(x1, x2, step):
            if HAS_NUMPY:
                pixel_rgb = [int(img[y, x, 0]), int(img[y, x, 1]), int(img[y, x, 2])]
            else:
                pixel = img.getpixel((x, y))
                pixel_rgb = list(pixel) if isinstance(pixel, tuple) else [pixel, pixel, pixel]
            
            # Проверка красного цвета с учетом реального цвета в точке (1590, 290)
            # В этой точке цвет [97, 28, 28] - темно-красный/бордовый
            r, g, b = pixel_rgb[0], pixel_rgb[1], pixel_rgb[2]
            
            # Основной критерий: проверка с реальным цветом из точки (1590, 290) [97, 28, 28]
            # Это темно-красный цвет награды
            matches_real = rgb_check(pixel_rgb, [97, 28, 28], mistake=25)
            
            # Альтернативные варианты похожих темно-красных цветов
            matches_variant1 = rgb_check(pixel_rgb, [100, 30, 30], mistake=25)
            matches_variant2 = rgb_check(pixel_rgb, [95, 25, 25], mistake=25)
            
            # Критерии для темно-красного цвета (на основе [97, 28, 28]):
            # Красный в диапазоне 80-120, зеленый и синий очень низкие (20-40)
            is_dark_red = (r >= 80 and r <= 120 and 
                          g >= 20 and g <= 50 and
                          b >= 20 and b <= 50 and
                          r > g + 50 and r > b + 50)
            
            # Ярко-красный вариант (для других случаев)
            is_bright_red = (r > 150 and g < 80 and b < 80 and 
                           r > g + 70 and r > b + 70)
            
            # Проверка с целевым RGB [218, 0, 0] с большим допуском
            matches_target = rgb_check(pixel_rgb, target_rgb, mistake=80)
            
            if matches_real or matches_variant1 or matches_variant2 or is_dark_red or is_bright_red or matches_target:
                red_dots.append((x, y, pixel_rgb))
    
    return red_dots


def draw_markers_on_image(img, markers, size=10):
    """Рисует маркеры на изображении"""
    if HAS_NUMPY:
        img_pil = Image.fromarray(img)
    else:
        img_pil = img.copy()
    
    draw = ImageDraw.Draw(img_pil)
    
    for marker in markers:
        if isinstance(marker, tuple) and len(marker) == 2:
            marker_type, (x, y) = marker
        else:
            # Старый формат для обратной совместимости
            marker_type = 'found'
            x, y = marker[0], marker[1]
        
        # Разные цвета для разных типов маркеров
        if marker_type == 'old':
            color = (0, 0, 255)  # Синий для старой точки
            label = "OLD"
        elif marker_type == 'new':
            color = (0, 255, 0)  # Зеленый для новой точки
            label = "NEW"
        else:
            color = (255, 0, 0)  # Красный для найденных точек
            label = "FOUND"
        
        # Рисуем круг
        draw.ellipse([x - size, y - size, x + size, y + size], 
                    outline=color, width=3)
        # Рисуем крестик
        draw.line([x - size*2, y, x + size*2, y], fill=color, width=3)
        draw.line([x, y - size*2, x, y + size*2], fill=color, width=3)
        
        # Добавляем текст с координатами
        try:
            draw.text((x + size + 5, y - size), f"{label} ({x},{y})", fill=color)
        except:
            pass  # Если нет шрифта, просто пропускаем
    
    if HAS_NUMPY:
        return np.array(img_pil)
    else:
        return img_pil


def test_claim_refill_coordinates(img, claim_refill):
    """Тестирует текущие координаты claim_refill"""
    x, y, expected_rgb = claim_refill[0], claim_refill[1], claim_refill[2]
    
    print(f"\n{'='*60}")
    print(f"ТЕСТ 1: Проверка текущих координат claim_refill")
    print(f"{'='*60}")
    print(f"Координаты: ({x}, {y})")
    print(f"Ожидаемый RGB: {expected_rgb}")
    
    matches, actual_rgb, max_diff = check_pixel_on_image(img, x, y, expected_rgb, mistake=10)
    
    print(f"Фактический RGB: {actual_rgb}")
    print(f"Максимальная разница: {max_diff}")
    print(f"Совпадение (mistake=10): {'✅ ДА' if matches else '❌ НЕТ'}")
    
    return matches, (x, y)


def test_red_dot_search(img, region, confidence=0.7):
    """Тестирует поиск красной точки через find_needle_red_dot"""
    print(f"\n{'='*60}")
    print(f"ТЕСТ 2: Поиск красной точки через find_needle_red_dot")
    print(f"{'='*60}")
    print(f"Область поиска: {region}")
    print(f"Confidence: {confidence}")
    
    # ВАЖНО: find_needle работает с экраном, а не с изображением
    # Для тестирования на скриншоте нужно использовать другой подход
    print("⚠️  find_needle работает только с активным экраном")
    print("   Для тестирования на скриншоте используем поиск по цвету")
    
    return None


def test_find_all_red_dots(img, region):
    """Находит все красные точки в области"""
    print(f"\n{'='*60}")
    print(f"ТЕСТ 3: Поиск всех красных точек в области")
    print(f"{'='*60}")
    print(f"Область поиска: {region}")
    
    red_dots = find_red_dots_in_region(img, region, target_rgb=[218, 0, 0], mistake=30)
    
    print(f"Найдено красных точек: {len(red_dots)}")
    
    if red_dots:
        print("\nКоординаты найденных точек:")
        for i, (x, y, rgb) in enumerate(red_dots, 1):
            print(f"  {i}. ({x}, {y}) - RGB: {rgb}")
    
    return red_dots


def save_result_image(img, markers, output_path):
    """Сохраняет изображение с маркерами"""
    marked_img = draw_markers_on_image(img, markers, size=10)
    if isinstance(marked_img, Image.Image):
        marked_img.save(output_path)
    else:
        result_img = Image.fromarray(marked_img)
        result_img.save(output_path)
    print(f"\n✅ Результат сохранен: {output_path}")


def main():
    if not HAS_PIL:
        print("\n❌ Ошибка: Pillow (PIL) необходим для работы скрипта")
        print("   Установите: pip install Pillow")
        print("   Или используйте виртуальное окружение проекта")
        return
    
    # Путь к папке со скриншотами
    screenshots_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)
    
    # Список доступных скриншотов
    screenshots = [f for f in os.listdir(screenshots_dir) 
                  if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not screenshots:
        print(f"❌ В папке {screenshots_dir} нет скриншотов!")
        print(f"   Поместите скриншот Live Arena в эту папку и запустите скрипт снова.")
        return
    
    print(f"\n📸 Доступные скриншоты:")
    for i, screenshot in enumerate(screenshots, 1):
        print(f"   {i}. {screenshot}")
    
    # Выбор скриншота
    choice = input(f"\nВыберите скриншот (1-{len(screenshots)}) или введите имя файла: ").strip()
    
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(screenshots):
            screenshot_file = screenshots[idx]
        else:
            print("❌ Неверный номер!")
            return
    else:
        screenshot_file = choice
        if screenshot_file not in screenshots:
            print(f"❌ Файл {screenshot_file} не найден!")
            return
    
    screenshot_path = os.path.join(screenshots_dir, screenshot_file)
    
    print(f"\n📷 Загружаю скриншот: {screenshot_file}")
    img, shape = load_screenshot(screenshot_path)
    print(f"✅ Размер изображения: {shape[1]}x{shape[0]}")
    
    # Текущие координаты claim_refill (старые)
    claim_refill_old = [875, 173, [218, 0, 0]]
    
    # Новые координаты от пользователя (X сдвинут левее на 10px: 1590 -> 1580)
    claim_refill_new = [1580, 290, [218, 0, 0]]
    
    # Тест 1: Проверка старых координат
    print(f"\n{'='*60}")
    print(f"ПРОВЕРКА СТАРЫХ КООРДИНАТ")
    print(f"{'='*60}")
    matches_old, claim_point_old = test_claim_refill_coordinates(img, claim_refill_old)
    
    # Тест 1.5: Проверка новых координат
    print(f"\n{'='*60}")
    print(f"ПРОВЕРКА НОВЫХ КООРДИНАТ (от пользователя)")
    print(f"{'='*60}")
    matches_new, claim_point_new = test_claim_refill_coordinates(img, claim_refill_new)
    
    # Тест 2: Поиск через find_needle (информационный)
    test_red_dot_search(img, None, confidence=0.7)
    
    # Тест 3: Показываем только маркер новой точки (1590, 290)
    print(f"\n💡 Показываем только маркер новой точки (1590, 290)")
    print(f"   Поиск других красных точек отключен")
    
    # Не ищем другие точки - только показываем маркер указанной точки
    
    # Создаем список маркеров для визуализации (только новая точка)
    markers = []
    if claim_point_old:
        markers.append(('old', claim_point_old))  # Старая точка (синяя)
    if claim_point_new:
        markers.append(('new', claim_point_new))  # Новая точка (зеленая)
    # Не добавляем другие красные точки - показываем только указанную точку
    
    # Сохраняем результат
    if markers:
        output_path = os.path.join(screenshots_dir, f"result_{screenshot_file}")
        save_result_image(img, markers, output_path)
        
        print(f"\n📊 Итоги:")
        print(f"   - Старая точка claim_refill [875, 173]: {'✅ найдена' if matches_old else '❌ не найдена'}")
        if claim_refill_new:
            new_x, new_y = claim_refill_new[0], claim_refill_new[1]
            print(f"   - Новая точка claim_refill [{new_x}, {new_y}]: {'✅ найдена' if matches_new else '❌ не найдена'}")
        if claim_point_new:
            print(f"   - Координаты для использования: ({claim_point_new[0]}, {claim_point_new[1]})")
    
    print(f"\n{'='*60}")
    print("✅ Тестирование завершено!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

