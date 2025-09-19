// Скрипт для страницы добавления велодорожки

// Глобальные переменные для карты
let map, drawnItems, drawControl, currentPolyline, citiesData;

/**
 * Загрузка данных о городах и заполнение селекта
 */
async function loadCitiesData() {
    try {
        console.log('Загрузка данных городов...');
        const response = await fetch('/static/data/cities.json');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        citiesData = await response.json();
        console.log('Города загружены:', citiesData.cities.length);
        
        // Заполняем селект городов
        populateCitySelect();
        
    } catch (error) {
        console.error('Ошибка загрузки городов:', error);
        
        // Fallback данные для JavaScript логики (под вашу структуру)
        citiesData = {
            cities: [
                { 
                    id: "almaty", 
                    name: "Алматы", 
                    country: "Казахстан",
                    distance: 0,
                    rating: 0,
                    coords: [43.2565, 76.9286], 
                    zoom: 12 
                }
            ]
        };
        
        console.log('Использованы fallback города');
        populateCitySelect();
    }
}

/**
 * Заполняет селект городов данными из JSON
 */
function populateCitySelect() {
    const citySelect = document.getElementById('city');
    if (!citySelect) {
        console.error('Селект городов не найден');
        return;
    }
    
    console.log('Заполнение селекта городов...');
    
    // Очищаем текущие опции (кроме первой "Выберите город")
    while (citySelect.children.length > 1) {
        citySelect.removeChild(citySelect.lastChild);
    }
    
    // Добавляем города из JSON
    citiesData.cities.forEach(city => {
        const option = document.createElement('option');
        option.value = city.id;
        option.textContent = city.name; // Просто "Алматы"
        citySelect.appendChild(option);
        
        console.log(`Добавлен город: ${city.name} (${city.id})`);
    });
    
    console.log(`Селект заполнен: ${citiesData.cities.length} городов`);
}

/**
 * Инициализация карты с функциональностью рисования
 */
function initMap() {
    console.log('Попытка инициализации карты...');
    
    // Проверяем, что элемент карты существует
    const mapElement = document.getElementById('map');
    if (!mapElement) {
        console.error('Элемент карты не найден');
        return;
    }
    
    console.log('Элемент карты найден, размеры:', mapElement.offsetWidth, 'x', mapElement.offsetHeight);

    try {
        // Создаем карту (центр - Алматы)
        map = L.map('map', {
            center: [43.2565, 76.9286],
            zoom: 12,
            zoomControl: true
        });
        
        console.log('Объект карты создан');
        
        // Добавляем тайлы OpenStreetMap
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);
        
        console.log('Тайлы добавлены');
        
        // Создаем слой для рисования
        drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);
        
        console.log('Слой для рисования создан');
        
        // Инициализируем функциональность рисования
        initDrawingHandlers();
        
        // Загружаем существующую геометрию если есть
        setTimeout(() => {
            loadExistingGeometry();
            // Принудительно обновляем размер карты
            map.invalidateSize();
        }, 500);
        
        console.log('Карта инициализирована успешно');
        
    } catch (error) {
        console.error('Ошибка при инициализации карты:', error);
    }
}

/**
 * Инициализация обработчиков для рисования линий
 */
function initDrawingHandlers() {
    let isDrawing = false;
    let currentPoints = [];
    
    console.log('Инициализация обработчиков рисования');
    
    // Обработчик клика по карте
    map.on('click', function(e) {
        console.log('Клик по карте:', e.latlng);
        
        if (!isDrawing) {
            startNewLine(e.latlng);
        } else {
            addPointToLine(e.latlng);
        }
    });
    
    // Обработчик двойного клика - завершение линии
    map.on('dblclick', function(e) {
        console.log('Двойной клик по карте');
        if (isDrawing) {
            // Останавливаем обработку клика после двойного клика
            setTimeout(() => {
                finishLine();
            }, 100);
        }
    });
    
    /**
     * Начинает рисование новой линии
     */
    function startNewLine(latlng) {
        console.log('Начало новой линии в точке:', latlng);
        
        // Очищаем предыдущие линии
        drawnItems.clearLayers();
        
        // Очищаем поле геометрии
        const geometryInput = document.getElementById('geometry');
        if (geometryInput) {
            geometryInput.value = '';
            console.log('Поле геометрии очищено');
        }
        
        // Начинаем новую линию
        currentPoints = [latlng];
        currentPolyline = L.polyline(currentPoints, {
            color: '#3498db',
            weight: 4,
            opacity: 0.8
        }).addTo(drawnItems);
        
        isDrawing = true;
        updateGeometryStatus('Кликайте по карте для добавления точек. Двойной клик завершит линию.', 'info');
    }
    
    /**
     * Добавляет точку к текущей линии
     */
    function addPointToLine(latlng) {
        console.log('Добавление точки:', latlng);
        currentPoints.push(latlng);
        currentPolyline.setLatLngs(currentPoints);
        
        console.log('Всего точек в линии:', currentPoints.length);
    }
    
    /**
     * Завершает рисование линии
     */
    function finishLine() {
        console.log('=== ЗАВЕРШЕНИЕ РИСОВАНИЯ ЛИНИИ ===');
        console.log('Количество точек:', currentPoints.length);
        console.log('Точки:', currentPoints);
        
        if (currentPoints.length < 2) {
            updateGeometryStatus('Линия должна содержать минимум 2 точки', 'invalid');
            console.log('ОШИБКА: Недостаточно точек');
            return;
        }
        
        isDrawing = false;
        
        // Создаем GeoJSON
        const coordinates = currentPoints.map(point => [point.lng, point.lat]);
        const geojson = {
            type: "LineString",
            coordinates: coordinates
        };
        
        console.log('Создан GeoJSON:', geojson);
        
        // Сохраняем в скрытое поле
        const geometryInput = document.getElementById('geometry');
        if (!geometryInput) {
            console.error('КРИТИЧЕСКАЯ ОШИБКА: Поле geometry не найдено!');
            return;
        }
        
        const geometryString = JSON.stringify(geojson);
        geometryInput.value = geometryString;
        
        console.log('ГЕОМЕТРИЯ СОХРАНЕНА:');
        console.log('- Поле найдено: ДА');
        console.log('- Значение установлено:', geometryString);
        console.log('- Проверяем значение поля сейчас:', geometryInput.value);
        console.log('- Длина:', geometryInput.value.length);
        
        // Делаем линию редактируемой
        if (currentPolyline && currentPolyline.editing) {
            currentPolyline.editing.enable();
            console.log('Редактирование линии включено');
            
            // Добавляем обработчик изменения линии
            currentPolyline.on('edit', function() {
                console.log('Линия отредактирована, обновляем геометрию');
                updateGeometryFromMap();
            });
        }
        
        // Принудительно обновляем геометрию из карты
        setTimeout(() => {
            console.log('Принудительное обновление геометрии через 100мс');
            updateGeometryFromMap();
        }, 100);
        
        // Обновляем статус
        validateGeometry();
        
        updateGeometryStatus('Линия нарисована! Можете перетаскивать точки для корректировки.', 'valid');
        
        console.log('=== ЗАВЕРШЕНИЕ ОБРАБОТКИ ЛИНИИ ===');
    }
}

/**
 * Загружает существующую геометрию из формы
 */
function loadExistingGeometry() {
    const existingGeometry = document.getElementById('geometry').value;
    if (existingGeometry) {
        try {
            const geojson = JSON.parse(existingGeometry);
            if (geojson.coordinates && geojson.coordinates.length > 1) {
                const latlngs = geojson.coordinates.map(coord => [coord[1], coord[0]]);
                const polyline = L.polyline(latlngs, {
                    color: '#3498db',
                    weight: 4,
                    opacity: 0.8
                }).addTo(drawnItems);
                
                if (polyline.editing) {
                    polyline.editing.enable();
                }
                
                // Подгоняем карту под линию
                map.fitBounds(polyline.getBounds());
                
                updateGeometryStatus('Линия загружена из сохраненных данных', 'valid');
            }
        } catch (e) {
            console.error('Ошибка при загрузке геометрии:', e);
        }
    }
}

/**
 * Валидация геометрии на сервере
 */
function validateGeometry() {
    const geometryValue = document.getElementById('geometry').value;
    
    if (!geometryValue) {
        return;
    }
    
    // Пока что простая клиентская валидация
    try {
        const geojson = JSON.parse(geometryValue);
        if (geojson.type === 'LineString' && geojson.coordinates && geojson.coordinates.length >= 2) {
            updateGeometryStatus('✓ Геометрия корректна', 'valid');
        } else {
            updateGeometryStatus('✗ Некорректная геометрия', 'invalid');
        }
    } catch (e) {
        updateGeometryStatus('✗ Ошибка в данных геометрии', 'invalid');
    }
}

/**
 * Обновляет статус геометрии
 */
function updateGeometryStatus(message, type) {
    const statusDiv = document.getElementById('geometry-status');
    if (statusDiv) {
        statusDiv.textContent = message;
        statusDiv.className = 'geometry-status ' + type;
        statusDiv.style.display = 'block';
    }
}

/**
 * Обновляет геометрию при редактировании линии
 */
function updateGeometryFromMap() {
    console.log('Обновление геометрии после редактирования...');
    
    if (!drawnItems) {
        console.log('drawnItems не найден');
        return;
    }
    
    const geometryInput = document.getElementById('geometry');
    if (!geometryInput) {
        console.log('Поле geometry не найдено');
        return;
    }
    
    drawnItems.eachLayer(function(layer) {
        if (layer instanceof L.Polyline) {
            const latlngs = layer.getLatLngs();
            console.log('Найдена полилиния с', latlngs.length, 'точками');
            
            const coordinates = latlngs.map(latlng => [latlng.lng, latlng.lat]);
            const geojson = {
                type: "LineString",
                coordinates: coordinates
            };
            
            const geometryString = JSON.stringify(geojson);
            geometryInput.value = geometryString;
            
            console.log('Геометрия обновлена:', geometryString);
        }
    });
}

/**
 * Инициализация обработки загрузки фотографий
 */
function initPhotoHandlers() {
    console.log('Инициализация обработчиков фото...');
    
    const uploadArea = document.getElementById('photo-upload-area');
    const fileInput = document.getElementById('photos');
    const preview = document.getElementById('photos-preview');
    
    console.log('Поиск элементов:');
    console.log('- uploadArea:', uploadArea ? 'найден' : 'НЕ НАЙДЕН');
    console.log('- fileInput:', fileInput ? 'найден' : 'НЕ НАЙДЕН');  
    console.log('- preview:', preview ? 'найден' : 'НЕ НАЙДЕН');
    
    if (!uploadArea || !fileInput || !preview) {
        console.error('Не все элементы найдены, прерываем инициализацию');
        return;
    }
    
    console.log('Все элементы найдены');
    
    // Используем только один обработчик - click
    uploadArea.addEventListener('click', function(e) {
        console.log('Клик по области загрузки');
        
        // Создаем временный input для обхода блокировки браузера
        const tempInput = document.createElement('input');
        tempInput.type = 'file';
        tempInput.multiple = true;
        tempInput.accept = 'image/*';
        tempInput.style.display = 'none';
        
        document.body.appendChild(tempInput);
        
        tempInput.addEventListener('change', function(e) {
            console.log('Файлы выбраны через временный input');
            const files = Array.from(e.target.files);
            
            if (files.length > 0) {
                // Копируем файлы в основной input
                const dt = new DataTransfer();
                files.forEach(file => dt.items.add(file));
                fileInput.files = dt.files;
                
                // Запускаем обработку
                handleFileSelection(files, fileInput, preview);
            }
            
            // Удаляем временный input
            document.body.removeChild(tempInput);
        });
        
        // Клик по временному input - это должно открыть диалог
        tempInput.click();
    });
    
    // Drag & Drop
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('Drag over');
        uploadArea.style.backgroundColor = '#f0f8ff';
        uploadArea.style.borderColor = '#3498db';
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('Drag leave');
        uploadArea.style.backgroundColor = '';
        uploadArea.style.borderColor = '';
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('Drop файлов');
        uploadArea.style.backgroundColor = '';
        uploadArea.style.borderColor = '';
        
        const files = Array.from(e.dataTransfer.files);
        console.log('Файлы из drop:', files.length);
        handleFileSelection(files, fileInput, preview);
    });
    
    // Обработка выбора файлов через основной input (если пользователь кликнет прямо по нему)
    fileInput.addEventListener('change', function(e) {
        console.log('Основной input change событие');
        console.log('Количество файлов:', e.target.files.length);
        
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            handleFileSelection(files, fileInput, preview);
        }
    });
    
    console.log('Обработчик клика привязан');
}

/**
 * Обработка выбранных файлов
 */
function handleFileSelection(files, fileInput, preview) {
    console.log('=== ОБРАБОТКА ФАЙЛОВ ===');
    console.log('Количество файлов:', files.length);
    
    // Очищаем предыдущий превью
    preview.innerHTML = '';
    
    if (files.length === 0) {
        console.log('Файлы не выбраны');
        return;
    }
    
    if (files.length > 10) {
        alert('Максимум 10 фотографий');
        fileInput.value = '';
        return;
    }
    
    let processedCount = 0;
    
    files.forEach((file, index) => {
        console.log(`Файл ${index + 1}:`, file.name, 'Тип:', file.type, 'Размер:', file.size);
        
        if (!file.type.startsWith('image/')) {
            console.log('Пропущен не-изображение:', file.name);
            return;
        }
        
        const reader = new FileReader();
        
        reader.onload = function(e) {
            console.log(`Файл ${index + 1} загружен в FileReader`);
            
            const photoDiv = document.createElement('div');
            photoDiv.className = 'photo-preview';
            photoDiv.innerHTML = `<img src="${e.target.result}" alt="Фото ${index + 1}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 4px;">`;
            
            preview.appendChild(photoDiv);
            processedCount++;
            
            console.log(`Фото ${index + 1} добавлено в превью (${processedCount}/${files.length})`);
            
            if (processedCount === files.filter(f => f.type.startsWith('image/')).length) {
                console.log('ВСЕ ФОТОГРАФИИ ОБРАБОТАНЫ УСПЕШНО!');
            }
        };
        
        reader.onerror = function(e) {
            console.error(`Ошибка загрузки файла ${index + 1}:`, e);
        };
        
        console.log(`Запуск FileReader для файла ${index + 1}`);
        reader.readAsDataURL(file);
    });
}

/**
 * Инициализация валидации формы
 */
function initFormValidation() {
    const form = document.getElementById('bikelane-form');
    if (!form) {
        console.error('Форма не найдена');
        return;
    }
    
    // Валидация формы перед отправкой
    form.addEventListener('submit', function(e) {
        console.log('=== ВАЛИДАЦИЯ ФОРМЫ ===');
        
        const city = document.getElementById('city').value;
        const title = document.getElementById('title').value.trim();
        const description = document.getElementById('description').value.trim();
        const trackType = document.querySelector('input[name="track_type"]:checked');
        const quality = document.querySelector('input[name="quality"]:checked');
        const geometryInput = document.getElementById('geometry');
        const geometry = geometryInput ? geometryInput.value : '';
        
        console.log('Проверка полей:');
        console.log('- Город:', city || 'НЕ ВЫБРАН');
        console.log('- Название:', title ? `"${title}" (${title.length} символов)` : 'ПУСТОЕ');
        console.log('- Описание:', description ? `${description.length} символов` : 'ПУСТОЕ');
        console.log('- Тип дорожки:', trackType ? trackType.value : 'НЕ ВЫБРАН');
        console.log('- Качество:', quality ? quality.value : 'НЕ ВЫБРАНО');
        console.log('- Геометрия поле найдено:', geometryInput ? 'ДА' : 'НЕТ');
        console.log('- Геометрия значение:', geometry ? 'ЕСТЬ' : 'ПУСТОЕ');
        console.log('- Геометрия длина:', geometry.length);
        console.log('- Геометрия содержимое:', geometry);
        
        let errors = [];
        
        if (!city) {
            errors.push('Необходимо выбрать город');
        }
        
        if (title.length < 3) {
            errors.push('Название должно содержать минимум 3 символа');
        }
        
        if (description.length < 20) {
            errors.push('Описание должно содержать минимум 20 символов');
        }
        
        if (!trackType) {
            errors.push('Необходимо выбрать тип дорожки');
        }
        
        if (!quality) {
            errors.push('Необходимо оценить качество покрытия');
        }
        
        if (!geometry || geometry.trim() === '') {
            errors.push('Необходимо нарисовать линию на карте');
            console.log('ОШИБКА: Геометрия пустая!');
        } else {
            // Проверяем что это валидный JSON
            try {
                const parsed = JSON.parse(geometry);
                if (!parsed.coordinates || parsed.coordinates.length < 2) {
                    errors.push('Линия должна содержать минимум 2 точки');
                    console.log('ОШИБКА: Недостаточно точек в геометрии');
                }
            } catch (e) {
                errors.push('Ошибка в данных геометрии');
                console.log('ОШИБКА: Некорректный JSON геометрии:', e);
            }
        }
        
        console.log('Результат валидации:', errors.length === 0 ? 'ВСЕ ОК' : 'ЕСТЬ ОШИБКИ');
        console.log('Ошибки:', errors);
        
        if (errors.length > 0) {
            e.preventDefault();
            alert('Ошибки в форме:\n' + errors.join('\n'));
            return false;
        }
        
        // Показываем индикатор загрузки
        const submitBtn = document.querySelector('.button_square_label.btn_black');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Отправка...';
            console.log('Кнопка заблокирована, форма отправляется');
        }
        
        // AJAX отправка формы
        e.preventDefault();
        
        const formData = new FormData(form);
        
        fetch(form.action || '/add-bikelane', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            console.log('Ответ сервера получен:', response.status);
            
            // Проверяем Content-Type ответа
            const contentType = response.headers.get('content-type');
            console.log('Content-Type:', contentType);
            
            if (contentType && contentType.includes('application/json')) {
                return response.json();
            } else {
                // Если сервер вернул HTML (страницу с ошибкой), считаем это ошибкой
                throw new Error('Сервер вернул HTML вместо JSON. Проверьте серверный код.');
            }
        })
        .then(data => {
            console.log('Данные от сервера:', data);
            
            if (data.success) {
                console.log('Форма успешно отправлена');
                showSuccessModal(data);
                
                // Очищаем форму
                form.reset();
                
                // Очищаем карту
                if (drawnItems) {
                    drawnItems.clearLayers();
                }
                
                // Очищаем геометрию
                const geometryInput = document.getElementById('geometry');
                if (geometryInput) {
                    geometryInput.value = '';
                }
                
                // Очищаем превью фотографий
                const preview = document.getElementById('photos-preview');
                if (preview) {
                    preview.innerHTML = '';
                }
                
                // Очищаем статус геометрии
                updateGeometryStatus('', 'info');
                
            } else {
                console.log('Сервер вернул ошибку:', data.error);
                alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            }
        })
        .catch(error => {
            console.error('Ошибка отправки:', error);
            alert('Ошибка при отправке формы: ' + error.message);
        })
        .finally(() => {
            // Восстанавливаем кнопку
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Отправить';
                console.log('Кнопка восстановлена');
            }
        });
    });
}

/**
 * Инициализация интерактивных элементов
 */
function initInteractiveElements() {
    // Автоматическое изменение центра карты при выборе города
    const citySelect = document.getElementById('city');
    if (citySelect) {
        citySelect.addEventListener('change', function() {
            const selectedCity = this.value;
            console.log('Выбран город:', selectedCity);
            
            if (selectedCity && citiesData && map) {
                const city = citiesData.cities.find(c => c.id === selectedCity);
                if (city) {
                    map.setView(city.coords, city.zoom || 12);
                    console.log('Карта перемещена к городу:', city.name);
                    console.log('Данные города:', {
                        country: city.country,
                        distance: city.distance,
                        rating: city.rating
                    });
                } else {
                    console.log('Данные города не найдены');
                }
            }
        });
    }
}

/**
 * Добавляет тестовую кнопку для отладки геометрии
 */
function addDebugButton() {
    if (console.log) {  // Только в режиме разработки
        const debugBtn = document.createElement('button');
        debugBtn.textContent = 'Debug Geometry';
        debugBtn.type = 'button';
        debugBtn.style.position = 'fixed';
        debugBtn.style.top = '10px';
        debugBtn.style.right = '10px';
        debugBtn.style.zIndex = '10000';
        debugBtn.style.padding = '5px 10px';
        debugBtn.style.fontSize = '12px';
        debugBtn.onclick = function() {
            const geometryInput = document.getElementById('geometry');
            console.log('=== DEBUG GEOMETRY ===');
            console.log('Поле найдено:', geometryInput ? 'ДА' : 'НЕТ');
            if (geometryInput) {
                console.log('Значение:', geometryInput.value);
                console.log('Длина:', geometryInput.value.length);
            }
            console.log('drawnItems слои:', drawnItems ? drawnItems.getLayers().length : 'drawnItems не найден');
        };
        document.body.appendChild(debugBtn);
    }
}

/**
 * Основная функция инициализации страницы
 */
async function initAddBikeLanePage() {
    console.log('Начало инициализации страницы');
    
    // Загружаем данные городов и заполняем селект
    await loadCitiesData();
    
    // Инициализируем компоненты
    initMap();
    initPhotoHandlers();
    initFormValidation();
    initInteractiveElements();
    
    // Добавляем тестовую кнопку для отладки геометрии
    addDebugButton();
    
    // Обновляем геометрию при редактировании (если карта инициализирована)
    if (map) {
        map.on('layeredit', updateGeometryFromMap);
    }
    
    console.log('Инициализация страницы завершена');
}

// Инициализация после загрузки страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM загружен, запуск инициализации');
    initAddBikeLanePage();
});

/**
 * Показывает модальное окно успешной отправки
 */
function showSuccessModal(data) {
    const modal = document.createElement('div');
    modal.className = 'success-modal-overlay';
    modal.innerHTML = `
        <div class="success-modal">
            <div class="success-modal-content">
                <div class="success-icon">
                    <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22,4 12,14.01 9,11.01"></polyline>
                    </svg>
                </div>
                
                <h2>Велодорожка отправлена!</h2>
                
                <p>Спасибо за ваш вклад в развитие велоинфраструктуры! Велодорожка будет проверена модераторами в течение 1-2 рабочих дней.</p>
                
                <div class="success-actions">
                    <button class="button_square_label btn_blue" onclick="location.reload()">
                        Добавить еще одну
                    </button>
                    <button class="button_square_label btn_outline" onclick="closeSuccessModal()">
                        Закрыть
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Добавляем стили если их еще нет
    if (!document.getElementById('success-modal-styles')) {
        const styles = document.createElement('style');
        styles.id = 'success-modal-styles';
        styles.textContent = `
            .success-modal-overlay {
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.5); display: flex; align-items: center;
                justify-content: center; z-index: 10000; opacity: 0;
                animation: fadeIn 0.3s ease forwards;
            }
            .success-modal {
                background: white; border-radius: 16px; padding: 2rem;
                max-width: 400px; width: 90%; text-align: center;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                transform: scale(0.8); animation: modalIn 0.3s ease 0.1s forwards;
            }
            .success-modal-content h2 { color: #2c3e50; margin: 1rem 0; font-size: 1.25rem; }
            .success-modal-content p { color: #666; line-height: 1.5; margin-bottom: 2rem; }
            .success-icon { margin-bottom: 1rem; }
            .success-icon svg { animation: checkmark 0.8s ease-in-out 0.3s forwards; opacity: 0; transform: scale(0); }
            .success-actions { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }
            .success-actions .button_square_label { padding: 0.75rem 1.5rem; border-radius: 50px; border: none; font-size: 0.9rem; font-weight: 600; cursor: pointer; transition: all 0.2s ease; }
            .btn_blue { background: #3498db; color: white; }
            .btn_blue:hover { background: #2980b9; transform: translateY(-1px); }
            .btn_outline { background: transparent; color: #666; border: 2px solid #e0e0e0; }
            .btn_outline:hover { background: #f8f9fa; border-color: #3498db; color: #3498db; }
            @keyframes fadeIn { to { opacity: 1; } }
            @keyframes modalIn { to { transform: scale(1); opacity: 1; } }
            @keyframes checkmark { 0% { transform: scale(0); opacity: 0; } 50% { transform: scale(1.2); } 100% { transform: scale(1); opacity: 1; } }
            @media (max-width: 480px) { .success-actions { flex-direction: column; } .success-modal { width: 95%; padding: 1.5rem; } }
        `;
        document.head.appendChild(styles);
    }
    
    document.body.appendChild(modal);
    
    modal.addEventListener('click', function(e) {
        if (e.target === modal) closeSuccessModal();
    });
}

/**
 * Закрывает модальное окно успеха
 */
function closeSuccessModal() {
    const modal = document.querySelector('.success-modal-overlay');
    if (modal) {
        modal.style.animation = 'fadeIn 0.3s ease reverse';
        setTimeout(() => modal.remove(), 300);
    }
}