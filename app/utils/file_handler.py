import os
import uuid
from io import BytesIO
from PIL import Image, ImageOps
from flask import current_app, flash

class FileHandler:
    """Обработчик загружаемых файлов"""
    
    @staticmethod
    def allowed_file(filename):
        """Проверка допустимого расширения файла"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
    
    @staticmethod
    def generate_unique_filename(filename):
        """Генерация уникального имени файла"""
        if not filename:
            return None
            
        # Получаем расширение
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
        
        # Генерируем уникальное имя
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        
        return unique_filename
    
    @staticmethod
    def create_upload_path(user_id, bikelane_id):
        """Создание пути для загрузки файлов"""
        upload_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'bikelanes',
            str(user_id or 'anonymous'),
            str(bikelane_id)
        )
        
        # Создаем директории если их нет
        os.makedirs(upload_path, exist_ok=True)
        
        return upload_path
    
    @staticmethod
    def compress_image_to_jpeg(
        image_path,
        max_size_kb,
        max_width=None,
        max_height=None,
        min_quality=35,
        min_dimension=64
    ):
        """Сжимает изображение в JPEG до заданного размера файла."""
        try:
            with Image.open(image_path) as img:
                img = ImageOps.exif_transpose(img)

                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    alpha = img.getchannel('A')
                    background.paste(img, mask=alpha)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                if max_width and max_height:
                    width, height = img.size
                    if width > max_width or height > max_height:
                        ratio = min(max_width / width, max_height / height)
                        new_size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)

                max_bytes = max_size_kb * 1024
                quality = 85

                while True:
                    candidate = FileHandler._encode_jpeg(img, quality)
                    if len(candidate) <= max_bytes:
                        break

                    if quality > min_quality:
                        quality = max(min_quality, quality - 5)
                        continue

                    width, height = img.size
                    if width <= min_dimension or height <= min_dimension:
                        return False

                    img = img.resize(
                        (max(1, int(width * 0.9)), max(1, int(height * 0.9))),
                        Image.Resampling.LANCZOS
                    )
                    quality = 80

                with open(image_path, 'wb') as output:
                    output.write(candidate)

            return True
            
        except Exception as e:
            current_app.logger.error(f"Ошибка при сжатии изображения: {e}")
            return False

    @staticmethod
    def _encode_jpeg(img, quality):
        output = BytesIO()
        img.save(output, 'JPEG', quality=quality, optimize=True, progressive=True)
        return output.getvalue()
    
    @staticmethod
    def save_uploaded_files(files, user_id, bikelane_id):
        """Сохранение загруженных файлов"""
        if not files:
            return []
        
        saved_files = []
        upload_path = FileHandler.create_upload_path(user_id, bikelane_id)
        
        # Ограничиваем количество файлов
        max_files = current_app.config['MAX_PHOTOS_PER_BIKELANE']
        files_to_process = files[:max_files]
        
        for file in files_to_process:
            if file and file.filename and FileHandler.allowed_file(file.filename):
                try:
                    # Генерируем безопасное имя файла
                    unique_filename = f"{uuid.uuid4().hex}.jpg"
                    file_path = os.path.join(upload_path, unique_filename)
                    
                    # Сохраняем файл
                    file.save(file_path)
                    
                    # Сжимаем изображение
                    if FileHandler.compress_image_to_jpeg(
                        file_path,
                        max_size_kb=120,
                        max_width=1920,
                        max_height=1080
                    ):
                        # Сохраняем относительный путь
                        relative_path = os.path.join(
                            'uploads/bikelanes',
                            str(user_id or 'anonymous'),
                            str(bikelane_id),
                            unique_filename
                        )
                        saved_files.append(relative_path)
                    else:
                        # Удаляем файл если не удалось обработать
                        os.remove(file_path)
                        flash(f"Ошибка при обработке файла {file.filename}", 'warning')
                
                except Exception as e:
                    current_app.logger.error(f"Ошибка при сохранении файла {file.filename}: {e}")
                    flash(f"Ошибка при сохранении файла {file.filename}", 'error')
            
            elif file and file.filename:
                flash(f"Неподдерживаемый формат файла: {file.filename}", 'warning')
        
        return saved_files

    @staticmethod
    def save_infrastructure_photos(files, infrastructure_id):
        """Сохранение фотографий велопарковки или ремонтной стойки."""
        if not files:
            return []

        relative_directory = os.path.join(
            'uploads',
            'infrastructure',
            str(infrastructure_id),
        )
        upload_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'infrastructure',
            str(infrastructure_id),
        )
        os.makedirs(upload_path, exist_ok=True)

        saved_files = []
        max_files = current_app.config['MAX_PHOTOS_PER_BIKELANE']

        for file in files[:max_files]:
            if not file or not file.filename:
                continue
            if not FileHandler.allowed_file(file.filename):
                flash(f"Неподдерживаемый формат файла: {file.filename}", 'warning')
                continue

            unique_filename = f"{uuid.uuid4().hex}.jpg"
            file_path = os.path.join(upload_path, unique_filename)
            try:
                file.save(file_path)
                if FileHandler.compress_image_to_jpeg(
                    file_path,
                    max_size_kb=120,
                    max_width=1920,
                    max_height=1080,
                ):
                    saved_files.append(
                        os.path.join(relative_directory, unique_filename)
                    )
                else:
                    os.remove(file_path)
                    flash(f"Ошибка при обработке файла {file.filename}", 'warning')
            except Exception as error:
                current_app.logger.error(
                    "Ошибка при сохранении файла %s: %s",
                    file.filename,
                    error,
                )
                if os.path.exists(file_path):
                    os.remove(file_path)
                flash(f"Ошибка при сохранении файла {file.filename}", 'error')

        return saved_files

    @staticmethod
    def save_review_photos(files, review_id):
        """Сохранение фотографий, приложенных к отзыву."""
        if not files:
            return []

        relative_directory = os.path.join(
            'uploads',
            'reviews',
            str(review_id),
        )
        upload_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'reviews',
            str(review_id),
        )
        os.makedirs(upload_path, exist_ok=True)

        saved_files = []
        max_files = current_app.config.get('MAX_PHOTOS_PER_REVIEW', 5)

        for file in files[:max_files]:
            if not file or not file.filename:
                continue
            if not FileHandler.allowed_file(file.filename):
                continue

            unique_filename = f"{uuid.uuid4().hex}.jpg"
            file_path = os.path.join(upload_path, unique_filename)
            try:
                file.save(file_path)
                if FileHandler.compress_image_to_jpeg(
                    file_path,
                    max_size_kb=120,
                    max_width=1920,
                    max_height=1080,
                ):
                    saved_files.append(
                        os.path.join(relative_directory, unique_filename)
                    )
                elif os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as error:
                current_app.logger.error(
                    "Ошибка при сохранении фото отзыва %s: %s",
                    file.filename,
                    error,
                )
                if os.path.exists(file_path):
                    os.remove(file_path)

        return saved_files
    
    @staticmethod
    def delete_file(file_path):
        """Удаление файла"""
        try:
            full_path = os.path.join(current_app.root_path, 'static', file_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
        except Exception as e:
            current_app.logger.error(f"Ошибка при удалении файла {file_path}: {e}")
        
        return False
