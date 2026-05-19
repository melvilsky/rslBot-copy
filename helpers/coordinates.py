import json
import os
from helpers.logging_utils import log_save


def load_coordinates(filename, required=False):
    """Load a coordinate JSON file from the coordinates/ directory."""
    path = os.path.join('coordinates', filename)
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                log_save(f"Loaded coordinates file: {path}")
                return data
        if required:
            raise RuntimeError(
                f'Не найден файл coordinates/{filename}. '
                'Скопируйте его из репозитория или восстановите.'
            )
        return None
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f'Ошибка загрузки координат из coordinates/{filename}: {e}') from e


def require_coordinate_files(*filenames):
    missing = [f'coordinates/{name}' for name in filenames if not os.path.exists(os.path.join('coordinates', name))]
    if missing:
        raise RuntimeError(
            'Не найдены файлы координат: {}. '
            'Скопируйте их из репозитория или восстановите.'.format(', '.join(missing))
        )


def get_coordinate(data, key, source='coordinates JSON', require_rgb=False):
    """
    Return [x, y] or [x, y, rgb] from a coordinate dict.
    Raises ValueError if the key or required rgb field is missing.
    """
    if not data or key not in data:
        raise ValueError(f"Coordinate '{key}' not found in {source}")
    coord = data[key]
    if require_rgb and 'rgb' not in coord:
        raise ValueError(f"Coordinate '{key}' in {source} must include rgb")
    if 'rgb' in coord:
        return [coord['x'], coord['y'], coord['rgb']]
    return [coord['x'], coord['y']]


def get_mistake(data, key, default=20):
    if data and key in data and isinstance(data[key], dict):
        return data[key].get('mistake', default)
    return default


def get_score_config(data, key, default_mistake=20, default_min_score=None):
    if not data or key not in data:
        return [], default_mistake, default_min_score

    coord = data[key]
    points = []
    for point in coord.get('points', []):
        if all(k in point for k in ('x', 'y', 'rgb')):
            points.append([point['x'], point['y'], point['rgb']])

    min_score = coord.get('min_score', default_min_score if default_min_score is not None else len(points))
    mistake = coord.get('mistake', default_mistake)
    return points, mistake, min_score


def parse_button_locations(data, key):
    return {int(k): [v['x'], v['y']] for k, v in data[key].items()}


def parse_point(data, key):
    point = data[key]
    return [point['x'], point['y']]
