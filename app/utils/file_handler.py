import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
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
    def resize_image(image_path, max_width=1920, max_height=1080, quality=85):
        """Изменение размера изображения"""
        try:
            with Image.open(image_path) as img:
                # Конвертируем в RGB если необходимо
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Вычисляем новые размеры с сохранением пропорций
                width, height = img.size
                
                if width > max_width or height > max_height:
                    ratio = min(max_width/width, max_height/height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Сохраняем с оптимизацией
                img.save(image_path, 'JPEG', quality=quality, optimize=True)
                
            return True
            
        except Exception as e:
            current_app.logger.error(f"Ошибка при изменении размера изображения: {e}")
            return False
    
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
                    unique_filename = FileHandler.generate_unique_filename(file.filename)
                    file_path = os.path.join(upload_path, unique_filename)
                    
                    # Сохраняем файл
                    file.save(file_path)
                    
                    # Изменяем размер изображения
                    if FileHandler.resize_image(file_path):
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
