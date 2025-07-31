import csv
import codecs
import asyncio
import logging
from aiohttp import ClientSession, ClientTimeout, BasicAuth
from tqdm.asyncio import tqdm_asyncio
from typing import List, Dict
from config import base_url, user, password
from config import data as dt

URL = f"{base_url}/wp-json/wp/v2"  # Глобальная переменная пути
WORKERS = 20  # Максимальное количество одновременно выполняемых задач
BATCH_SIZE = 50  # Размер батча задач

# Логгирование
logging.basicConfig(level=logging.WARN, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Установка тайм-аута
timeout = ClientTimeout(
    total=2400,  # Общее время выполнения (секунды)
    connect=240,  # Время ожидания подключения (секунды)
    sock_read=1200,  # Время ожидания чтения данных (секунды)
    sock_connect=240  # Время ожидания установки соединения (секунды)
)


def custom_replacement(error):
    """Обработчик ошибок декодирования. Заменяет некорректные символы на указанный символ."""
    replacement_char = ' '  # Символ для замены
    return replacement_char, error.start + 1


# Регистрируем пользовательский обработчик ошибок
codecs.register_error('custom_replace', custom_replacement)


def save_file(filename: str, data: List[List[str]]):
    """Сохраняет данные в CSV."""
    with open(f"{filename}_posted.csv", 'w', newline='', encoding='utf-8', errors='custom_replace') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')
        writer.writerows(data)


async def get_existing_tags(session: ClientSession, tag) -> Dict[str, int]:
    """Получает список существующих тегов из WordPress."""
    tags = {}
    params = {"search": tag, "per_page": 100}
    async with session.get(
            f"{URL}/tags",
            auth=BasicAuth(user, password),
            params=params
    ) as resp:
        if resp.status == 200:
            data = await resp.json()
            # Приводим имя тега к нижнему регистру для корректного сравнения
            tags = {tag["name"].lower(): tag["id"] for tag in data}
        else:
            print(resp.text)
    return tags


async def create_tag(session: ClientSession, tag_name: str) -> int:
    """Создает тег в WordPress и возвращает его ID."""
    async with session.post(
        f"{URL}/tags",
        auth=BasicAuth(user, password),
        json={"name": tag_name}
    ) as resp:
        if resp.status == 201:
            tag_data = await resp.json()
            logger.info(f"Новый тег '{tag_name}' id:{tag_data['id']} создан успешно.")
            return tag_data["id"]
    return None


async def process_tags(session: ClientSession, post: Dict[str, str]) -> Dict[str, int]:
    """Возвращается словарь с тегами и их ID"""
    tags_dict = {}
    tags_list = [tag.strip().lower() for tag in post['tags'].split(',') if tag.strip()]
    for tag in tags_list:
        if tag not in tags_dict:
            existing_tags = await get_existing_tags(session, tag)
            if tag in existing_tags:
                tags_dict[tag] = existing_tags[tag]
            else:
                tag_id = await create_tag(session, tag)
                if tag_id:
                    tags_dict[tag] = tag_id
    return tags_dict


# Функции для работы с файлами
def get_data(file_path: str) -> List[Dict[str, str]]:
    """Считывает данные из CSV и возвращает список словарей."""
    data = []
    with open(f"{file_path}.csv", newline='', encoding='utf-8', errors='custom_replace') as url_csvfile:
        reader = csv.reader(url_csvfile, delimiter=';')
        next(reader)  # Пропускаем заголовок
        for row in reader:
            # category, name, description, tags, img_path, product_link = row
            category, name, description, img_path, product_link = row
            product_link = product_link + f'ref/10179364/?campaign={file_path}'
            img_path = img_path.strip().strip('"\'')
            if img_path:
                # data.append({'category': category, 'name': name, 'description': description,'tags': tags,'img_path': img_path,'product_link': product_link})
                data.append({'category': category,
                             'name': name,
                             'description': description,
                             'img_path': img_path,
                             'product_link': product_link
                             })
    return data


# Асинхронные задачи
async def upload_image(session: ClientSession, post: Dict[str, str]) -> int:
    """Загружает изображение и возвращает ID."""
    while True:
        with open(post['img_path'], 'rb') as f:
            # file_data = {'file': f}
            data = {
                'file': f,
                'caption': post['name'],
                'description': post['description'],
                'alt_text': post['name']
            }

            async with session.post(f"{URL}/media", auth=BasicAuth(user, password), data=data) as resp:
                if resp.status == 201:
                    image_data = await resp.json()
                    logger.info(f"Изображение id:{image_data['id']} '{post['name']}' загружено успешно.")
                    return image_data['id']
                else:
                    logger.error(f"Ошибка загрузки изображения '{post['name']}': {resp.status}")
                    await asyncio.sleep(5)


async def create_post(session: ClientSession, post: Dict[str, str], image_id: int) -> str:
    """Создает пост и возвращает ссылку на него."""
    if image_id:
        count = 0
        # """Создаём словарь тегов по всему файлу"""
        # tags_dict = await process_tags(session, post)
        # tags = [tag.strip().lower() for tag in post['tags'].split(',') if tag.strip()]
        # tag_ids = [tags_dict[tag] for tag in tags if tag in tags_dict]
        while count < 5:
            new_html = dt.replace('{description}', post['description']).replace('{product_link}', post['product_link'])
            data = {
                'title': post['name'],
                'status': 'publish',
                'content': new_html,
                'featured_media': image_id,
                'categories': int(post['category']),
                # 'tags': tag_ids
            }

            async with session.post(f"{URL}/posts", auth=BasicAuth(user, password), json=data) as resp:
                try:
                    if resp.status == 201:
                        post_data = await resp.json()
                        logger.info(f"Пост '{post['name']}' успешно создан.")
                        return post_data['guid']['rendered']
                    else:
                        logger.error(f"Ошибка создания поста '{post['name']}': {resp.status}")
                        count += 1
                        await asyncio.sleep(5)
                except RuntimeWarning as ex:
                    logger.error(f"RuntimeWarning Ошибка создания поста '{post['name']}': \n{ex}")
                    count += 1
                    await asyncio.sleep(5)
        return None


async def process_single_post(session: ClientSession, post: Dict[str, str]) -> List[str]:
    """Обрабатывает одиночный пост: загружает изображение и создаёт запись."""
    count = 0
    try:
        image_id = await upload_image(session, post)
    except Exception as ex:
        image_id = None
        logger.error(f"Ошибка загрузки изображения '{post['img_path']}': \n{ex}")
        await asyncio.sleep(5)

    while count < 5:
        try:
            if image_id is None:
                image_id = await upload_image(session, post)
            if image_id:
                post_url = await create_post(session, post, image_id)
                if post_url:
                    # return [post['category'], post['name'], post['description'], post['tags'], post['img_path'],
                    #         post_url, post['product_link']]
                    return [post['category'], post['name'], post['description'], post['img_path'], post_url,
                            post['product_link']]
        except Exception as ex:
            logger.error(f"\nОбщая ошибка создания поста '{post['name']}': \n{ex}")
            count += 1
            await asyncio.sleep(5)

    return None


async def process_posts():
    """Основной процесс обработки постов."""
    csv_file = 'unique_photoshop_actions'
    post_data = get_data(csv_file)
    # result_data = [['category', 'name', 'description', 'tags', 'img_path', 'product_link', 'post_link']]
    result_data = [['category', 'name', 'description', 'img_path', 'product_link', 'post_link']]
    semaphore = asyncio.Semaphore(WORKERS)

    async def limited_process(post):
        """Ограничивает выполнение задач с помощью семафора."""
        async with semaphore:
            return await process_single_post(session, post)
    try:
        async with ClientSession(timeout=timeout) as session:
            """Используем tqdm_asyncio для управления прогрессом"""
            tasks = [limited_process(post) for post in post_data]
            logger.critical(f'tasks = {len(tasks)}')

            for i in range(0, len(tasks), BATCH_SIZE):
                batch = tasks[i:i + BATCH_SIZE]
                try:
                    for result in await tqdm_asyncio.gather(*batch, desc=f"Processing posts {i}-{i + len(batch)}",
                                                            total=len(batch)):
                        if result:
                            result_data.append(result)
                except Exception as ex:
                    logger.error(f'{ex} \nresult_data = {result_data}')
    except Exception as ex:
        logger.error(f'Error in posting:\n{ex} \nPosted articles = {len(result_data)}')
    finally:
        save_file(csv_file, result_data)

if __name__ == '__main__':
    asyncio.run(process_posts())
