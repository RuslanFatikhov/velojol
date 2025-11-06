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

    // Fallback данные
    citiesData = {
      cities: [
        {
          id: 'almaty',
          name: 'Алматы',
          country: 'Казахстан',
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

  // Очищаем текущие опции (кроме первой "Выберите город")
  while (citySelect.children.length > 1) {
    citySelect.removeChild(citySelect.lastChild);
  }

  // Добавляем города из JSON
  citiesData.cities.forEach((city) => {
    const option = document.createElement('option');
    option.value = city.id;
    option.textContent = city.name;
    citySelect.appendChild(option);
  });

  console.log(`Селект заполнен: ${citiesData.cities.length} городов`);
}

/**
 * Рассчитывает дистанцию линии в метрах по координатам [lon, lat]
 */
function calculateLineDistance(coordinates) {
  if (!coordinates || coordinates.length < 2) {
    return 0;
  }

  let totalDistance = 0;

  for (let i = 0; i < coordinates.length - 1; i++) {
    const [lon1, lat1] = coordinates[i];
    const [lon2, lat2] = coordinates[i + 1];

    const distance = haversineDistance(lat1, lon1, lat2, lon2);
    totalDistance += distance;
  }

  return totalDistance;
}

/**
 * Формула гаверсинуса для расчета расстояния между двумя точками
 */
function haversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371000; // Радиус Земли в метрах

  const toRad = (x) => (x * Math.PI) / 180;

  const dlat = toRad(lat2 - lat1);
  const dlon = toRad(lon2 - lon1);

  const a =
    Math.sin(dlat / 2) * Math.sin(dlat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dlon / 2) * Math.sin(dlon / 2);

  const c = 2 * Math.asin(Math.sqrt(a));

  return R * c;
}

/**
 * Форматирует дистанцию для отображения
 */
function formatDistance(distanceInMeters) {
  if (distanceInMeters >= 1000) {
    return `${(distanceInMeters / 1000).toFixed(1)} км`;
  } else {
    return `${Math.round(distanceInMeters)} м`;
  }
}

/**
 * Рассчитывает общее качество велодорожки
 */
function calculateOverallQuality() {
  console.log('Расчет общего качества велодорожки...');

  const trackTypeInput = document.querySelector('input[name="track_type"]:checked');
  if (!trackTypeInput) {
    console.log('Тип велодорожки не выбран');
    return null;
  }
  const trackType = trackTypeInput.value;

  const qualityInput = document.querySelector('input[name="quality"]:checked');
  if (!qualityInput) {
    console.log('Качество покрытия не выбрано');
    return null;
  }
  const surfaceQuality = parseInt(qualityInput.value);

  const hasParking = document.getElementById('has_parking')?.checked ?? false;
  const hasMarkings = document.getElementById('has_markings')?.checked ?? false;
  const hasSigns = document.getElementById('has_signs')?.checked ?? false;

  const baseQuality = {
    separated: 5,
    bollards: 4,
    lane: 3,
    shared: 3
  };

  let quality = baseQuality[trackType] || 3;

  if (hasParking) {
    quality -= 1;
    console.log('Паркуются авто: -1 балл');
  }

  if (hasMarkings) {
    quality += 0.5;
    console.log('Есть разметка: +0.5 балла');
  }

  if (hasSigns) {
    quality += 0.5;
    console.log('Есть знаки: +0.5 балла');
  }

  if (surfaceQuality <= 2) {
    quality -= 1;
    console.log('Плохое покрытие: -1 балл');
  } else if (surfaceQuality >= 4) {
    quality += 1;
    console.log('Хорошее покрытие: +1 балл');
  }

  quality = Math.max(1, Math.min(5, Math.round(quality)));

  console.log('Итоговое качество:', quality);

  return quality;
}

/**
 * Обновляет отображение качества велодорожки
 */
function updateQualityDisplay() {
  const quality = calculateOverallQuality();

  const section = document.getElementById('quality-display-section');
  if (quality === null) {
    if (section) section.style.display = 'none';
    return;
  }
  if (section) section.style.display = 'block';

  const starsContainer = document.getElementById('quality-stars');
  if (starsContainer) {
    starsContainer.innerHTML = '';
    for (let i = 1; i <= 5; i++) {
      const star = document.createElement('span');
      star.className = i <= quality ? 'quality-star' : 'quality-star empty';
      star.textContent = '★';
      starsContainer.appendChild(star);
    }
  }

  const descriptions = {
    1: 'Очень плохое качество. Велодорожка требует серьезного улучшения.',
    2: 'Низкое качество. Есть значительные проблемы.',
    3: 'Среднее качество. Приемлемо для использования.',
    4: 'Хорошее качество. Комфортно для велосипедистов.',
    5: 'Отличное качество. Идеальная велоинфраструктура!'
  };

  const descriptionElement = document.getElementById('quality-description');
  if (descriptionElement) {
    descriptionElement.textContent = descriptions[quality] || '';
  }

  const qualityInput = document.getElementById('overall_quality');
  if (qualityInput) {
    qualityInput.value = quality;
  }

  console.log('Отображение качества обновлено:', quality);
}

/**
 * Обновляет отображение дистанции
 */
function updateDistanceDisplay(coordinates) {
  const distance = calculateLineDistance(coordinates);
  const formattedDistance = formatDistance(distance);

  let distanceElement = document.getElementById('distance-display');
  if (!distanceElement) {
    distanceElement = document.createElement('div');
    distanceElement.id = 'distance-display';
    distanceElement.className = 'distance-display';

    const geometryStatus = document.getElementById('geometry-status');
    if (geometryStatus && geometryStatus.parentNode) {
      geometryStatus.parentNode.insertBefore(distanceElement, geometryStatus.nextSibling);
    }
  }

  distanceElement.innerHTML = `
    <span class="distance-label">Дистанция:</span>
    <span class="distance-value">${formattedDistance}</span>
  `;

  console.log(`Дистанция обновлена: ${formattedDistance} (${distance.toFixed(2)} м)`);

  return distance;
}

/**
 * Добавляет скрытое поле для дистанции в форму
 */
function addDistanceField(distance) {
  let distanceInput = document.getElementById('distance');
  if (!distanceInput) {
    distanceInput = document.createElement('input');
    distanceInput.type = 'hidden';
    distanceInput.id = 'distance';
    distanceInput.name = 'distance';

    const form = document.getElementById('bikelane-form');
    if (form) {
      form.appendChild(distanceInput);
    }
  }

  distanceInput.value = distance.toFixed(2);
  console.log(`Поле distance установлено: ${distance.toFixed(2)} м`);
}

/**
 * Инициализация карты с функциональностью рисования
 */
function initMap() {
  console.log('Попытка инициализации карты...');

  const mapElement = document.getElementById('map');
  if (!mapElement) {
    console.error('Элемент карты не найден');
    return;
  }

  console.log('Элемент карты найден, размеры:', mapElement.offsetWidth, 'x', mapElement.offsetHeight);

  try {
    map = L.map('map', {
      center: [43.2565, 76.9286],
      zoom: 12,
      zoomControl: true
    });

    console.log('Объект карты создан');

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(map);

    console.log('Тайлы добавлены');

    drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    console.log('Слой для рисования создан');

    initDrawingHandlers();

    setTimeout(() => {
      loadExistingGeometry();
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

  const finishBtn = document.getElementById('finish-line-btn');
  const resetBtn = document.getElementById('reset-line-btn');
  const mapControls = document.getElementById('map-controls');
  console.log('Кнопки найдены:', !!finishBtn, !!resetBtn, !!mapControls);

  map.on('click', function (e) {
    console.log('Клик по карте:', e.latlng);

    if (!isDrawing) {
      startNewLine(e.latlng);
    } else {
      addPointToLine(e.latlng);
    }
  });

  map.on('dblclick', function () {
    console.log('Двойной клик по карте');
    if (isDrawing) {
      setTimeout(() => {
        finishLine();
      }, 100);
    }
  });

  if (finishBtn) finishBtn.addEventListener('click', () => isDrawing && finishLine());
  if (resetBtn) resetBtn.addEventListener('click', resetLine);

  /**
   * Начинает рисование новой линии
   */
  function startNewLine(latlng) {
    console.log('Начало новой линии в точке:', latlng);

    drawnItems.clearLayers();

    const geometryInput = document.getElementById('geometry');
    if (geometryInput) {
      geometryInput.value = '';
      console.log('Поле геометрии очищено');
    }

    const distanceElement = document.getElementById('distance-display');
    if (distanceElement) {
      distanceElement.style.display = 'none';
    }

    currentPoints = [latlng];
    currentPolyline = L.polyline(currentPoints, {
      color: '#3498db',
      weight: 4,
      opacity: 0.8
    }).addTo(drawnItems);

    isDrawing = true;

    if (mapControls) {
      mapControls.style.display = 'none';
    }
    updateGeometryStatus(
      'Кликайте по карте для добавления точек. Двойной клик завершит линию.',
      'info'
    );
  }

  /**
   * Добавляет точку к текущей линии
   */
  function addPointToLine(latlng) {
    console.log('Добавление точки:', latlng);
    currentPoints.push(latlng);
    currentPolyline.setLatLngs(currentPoints);

    console.log('Всего точек в линии:', currentPoints.length);

    if (currentPoints.length >= 2 && mapControls) {
      mapControls.style.display = 'flex';
      console.log('Кнопки управления показаны');
    }
  } // ← ВАЖНО: закрывающая скобка для addPointToLine

  /**
   * Сбрасывает рисование линии
   */
  function resetLine() {
    console.log('=== СБРОС РИСОВАНИЯ ЛИНИИ ===');

    if (drawnItems) {
      drawnItems.clearLayers();
    }

    currentPoints = [];
    currentPolyline = null;
    isDrawing = false;

    if (mapControls) {
      mapControls.style.display = 'none';
    }

    const geometryInput = document.getElementById('geometry');
    if (geometryInput) {
      geometryInput.value = '';
      console.log('Поле геометрии очищено');
    }

    const distanceElement = document.getElementById('distance-display');
    if (distanceElement) {
      distanceElement.style.display = 'none';
    }

    updateGeometryStatus('Кликните по карте для начала рисования линии', 'info');

    console.log('=== СБРОС ЗАВЕРШЕН ===');
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

    if (mapControls) {
      mapControls.style.display = 'none';
    }

    const coordinates = currentPoints.map((point) => [point.lng, point.lat]);
    const geojson = {
      type: 'LineString',
      coordinates: coordinates
    };

    console.log('Создан GeoJSON:', geojson);

    const distance = updateDistanceDisplay(coordinates);
    addDistanceField(distance);

    const geometryInput = document.getElementById('geometry');
    if (!geometryInput) {
      console.error('КРИТИЧЕСКАЯ ОШИБКА: Поле geometry не найдено!');
      return;
    }

    const geometryString = JSON.stringify(geojson);
    geometryInput.value = geometryString;

    console.log('ГЕОМЕТРИЯ СОХРАНЕНА:', geometryString);

    if (currentPolyline && currentPolyline.editing) {
      currentPolyline.editing.enable();
      console.log('Редактирование линии включено');

      currentPolyline.on('edit', function () {
        console.log('Линия отредактирована, обновляем геометрию и дистанцию');
        updateGeometryFromMap();
      });
    }

    setTimeout(() => {
      console.log('Принудительное обновление геометрии через 100мс');
      updateGeometryFromMap();
    }, 100);

    validateGeometry();

    updateGeometryStatus(
      `Линия нарисована! Дистанция: ${formatDistance(
        distance
      )}. Можете перетаскивать точки для корректировки.`,
      'valid'
    );

    console.log('=== ЗАВЕРШЕНИЕ ОБРАБОТКИ ЛИНИИ ===');
  }
}

/**
 * Загружает существующую геометрию из формы
 */
function loadExistingGeometry() {
  const geometryEl = document.getElementById('geometry');
  const existingGeometry = geometryEl ? geometryEl.value : '';
  if (existingGeometry) {
    try {
      const geojson = JSON.parse(existingGeometry);
      if (geojson.coordinates && geojson.coordinates.length > 1) {
        const latlngs = geojson.coordinates.map((coord) => [coord[1], coord[0]]);
        const polyline = L.polyline(latlngs, {
          color: '#3498db',
          weight: 4,
          opacity: 0.8
        }).addTo(drawnItems);

        if (polyline.editing) {
          polyline.editing.enable();
        }

        map.fitBounds(polyline.getBounds());

        const distance = updateDistanceDisplay(geojson.coordinates);
        addDistanceField(distance);

        updateGeometryStatus('Линия загружена из сохраненных данных', 'valid');
      }
    } catch (e) {
      console.error('Ошибка при загрузке геометрии:', e);
    }
  }
}

/**
 * Валидация геометрии (клиентская)
 */
function validateGeometry() {
  const geometryInput = document.getElementById('geometry');
  const geometryValue = geometryInput ? geometryInput.value : '';

  if (!geometryValue) {
    updateGeometryStatus('✗ Геометрия отсутствует', 'invalid');
    return false;
  }

  try {
    const geojson = JSON.parse(geometryValue);
    if (geojson.type === 'LineString' && geojson.coordinates && geojson.coordinates.length >= 2) {
      updateGeometryStatus('✓ Геометрия корректна', 'valid');
      return true;
    } else {
      updateGeometryStatus('✗ Некорректная геометрия', 'invalid');
      return false;
    }
  } catch (e) {
    updateGeometryStatus('✗ Ошибка в данных геометрии', 'invalid');
    return false;
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

  drawnItems.eachLayer(function (layer) {
    if (layer instanceof L.Polyline) {
      const latlngs = layer.getLatLngs();
      console.log('Найдена полилиния с', latlngs.length, 'точками');

      const coordinates = latlngs.map((latlng) => [latlng.lng, latlng.lat]);
      const geojson = {
        type: 'LineString',
        coordinates: coordinates
      };

      const geometryString = JSON.stringify(geojson);
      geometryInput.value = geometryString;

      const distance = updateDistanceDisplay(coordinates);
      addDistanceField(distance);

      console.log('Геометрия и дистанция обновлены:', geometryString);
      console.log('Новая дистанция:', distance.toFixed(2), 'м');
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

  uploadArea.addEventListener('click', function () {
    console.log('Клик по области загрузки');

    const tempInput = document.createElement('input');
    tempInput.type = 'file';
    tempInput.multiple = true;
    tempInput.accept = 'image/*';
    tempInput.style.display = 'none';

    document.body.appendChild(tempInput);

    tempInput.addEventListener('change', function (e) {
      console.log('Файлы выбраны через временный input');
      const files = Array.from(e.target.files);

      if (files.length > 0) {
        const dt = new DataTransfer();
        files.forEach((file) => dt.items.add(file));
        fileInput.files = dt.files;

        handleFileSelection(files, fileInput, preview);
      }

      document.body.removeChild(tempInput);
    });

    tempInput.click();
  });

  // Drag & Drop
  uploadArea.addEventListener('dragover', function (e) {
    e.preventDefault();
    e.stopPropagation();
    console.log('Drag over');
    uploadArea.style.backgroundColor = '#f0f8ff';
    uploadArea.style.borderColor = '#3498db';
  });

  uploadArea.addEventListener('dragleave', function (e) {
    e.preventDefault();
    e.stopPropagation();
    console.log('Drag leave');
    uploadArea.style.backgroundColor = '';
    uploadArea.style.borderColor = '';
  });

  uploadArea.addEventListener('drop', function (e) {
    e.preventDefault();
    e.stopPropagation();
    console.log('Drop файлов');
    uploadArea.style.backgroundColor = '';
    uploadArea.style.borderColor = '';

    const files = Array.from(e.dataTransfer.files);
    console.log('Файлы из drop:', files.length);
    handleFileSelection(files, fileInput, preview);
  });

  // Обработка выбора файлов через основной input
  fileInput.addEventListener('change', function (e) {
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

    reader.onload = function (e) {
      console.log(`Файл ${index + 1} загружен в FileReader`);

      const photoDiv = document.createElement('div');
      photoDiv.className = 'photo-preview';
      photoDiv.innerHTML = `<img src="${e.target.result}" alt="Фото ${index + 1}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 4px;">`;

      preview.appendChild(photoDiv);
      processedCount++;

      console.log(`Фото ${index + 1} добавлено в превью (${processedCount}/${files.length})`);

      if (processedCount === files.filter((f) => f.type.startsWith('image/')).length) {
        console.log('ВСЕ ФОТОГРАФИИ ОБРАБОТАНЫ УСПЕШНО!');
      }
    };

    reader.onerror = function (e) {
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

  form.addEventListener('submit', function (e) {
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

    let errors = [];

    if (!city) errors.push('Необходимо выбрать город');
    if (title.length < 3) errors.push('Название должно содержать минимум 3 символа');
    if (description.length < 20) errors.push('Описание должно содержать минимум 20 символов');
    if (!trackType) errors.push('Необходимо выбрать тип дорожки');
    if (!quality) errors.push('Необходимо оценить качество покрытия');

    if (!geometry || geometry.trim() === '') {
      errors.push('Необходимо нарисовать линию на карте');
      console.log('ОШИБКА: Геометрия пустая!');
    } else {
      try {
        const parsed = JSON.parse(geometry);
        if (!parsed.coordinates || parsed.coordinates.length < 2) {
          errors.push('Линия должна содержать минимум 2 точки');
          console.log('ОШИБКА: Недостаточно точек в геометрии');
        } else {
          const distance = calculateLineDistance(parsed.coordinates);
          if (distance < 10) {
            errors.push('Велодорожка должна быть длиннее 10 метров');
            console.log('ОШИБКА: Дистанция слишком мала:', distance.toFixed(2), 'м');
          }
        }
      } catch (err) {
        errors.push('Ошибка в данных геометрии');
        console.log('ОШИБКА: Некорректный JSON геометрии:', err);
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
      .then((response) => {
        console.log('Ответ сервера получен:', response.status);

        const contentType = response.headers.get('content-type');
        console.log('Content-Type:', contentType);

        if (contentType && contentType.includes('application/json')) {
          return response.json();
        } else {
          throw new Error('Сервер вернул HTML вместо JSON. Проверьте серверный код.');
        }
      })
      .then((data) => {
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
          const geometryInput2 = document.getElementById('geometry');
          if (geometryInput2) {
            geometryInput2.value = '';
          }

          // Очищаем превью фотографий
          const preview = document.getElementById('photos-preview');
          if (preview) {
            preview.innerHTML = '';
          }

          // Очищаем статус геометрии и дистанцию
          updateGeometryStatus('', 'info');
          const distanceElement = document.getElementById('distance-display');
          if (distanceElement) {
            distanceElement.style.display = 'none';
          }
        } else {
          console.log('Сервер вернул ошибку:', data.error);
          alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
        }
      })
      .catch((error) => {
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
    citySelect.addEventListener('change', function () {
      const selectedCity = this.value;
      console.log('Выбран город:', selectedCity);

      if (selectedCity && citiesData && map) {
        const city = citiesData.cities.find((c) => c.id === selectedCity);
        if (city) {
          map.setView(city.coords, city.zoom || 12);
          console.log('Карта перемещена к городу:', city.name);
        } else {
          console.log('Данные города не найдены');
        }
      }
    });
  }
}

/**
 * Инициализация обработчиков для обновления качества
 */
function initQualityHandlers() {
  console.log('Инициализация обработчиков качества...');

  const trackTypeInputs = document.querySelectorAll('input[name="track_type"]');
  trackTypeInputs.forEach((input) => {
    input.addEventListener('change', function () {
      console.log('Изменен тип велодорожки:', this.value);
      updateQualityDisplay();
    });
  });

  const qualityInputs = document.querySelectorAll('input[name="quality"]');
  qualityInputs.forEach((input) => {
    input.addEventListener('change', function () {
      console.log('Изменено качество покрытия:', this.value);
      updateQualityDisplay();
    });
  });

  const parkingToggle = document.getElementById('has_parking');
  if (parkingToggle) {
    parkingToggle.addEventListener('change', function () {
      console.log('Изменена парковка:', this.checked);
      const hidden = document.getElementById('has_parking_hidden');
      if (hidden) hidden.value = this.checked;
      updateQualityDisplay();
    });
  }

  const markingsToggle = document.getElementById('has_markings');
  if (markingsToggle) {
    markingsToggle.addEventListener('change', function () {
      console.log('Изменена разметка:', this.checked);
      const hidden = document.getElementById('has_markings_hidden');
      if (hidden) hidden.value = this.checked;
      updateQualityDisplay();
    });
  }

  const signsToggle = document.getElementById('has_signs');
  if (signsToggle) {
    signsToggle.addEventListener('change', function () {
      console.log('Изменены знаки:', this.checked);
      const hidden = document.getElementById('has_signs_hidden');
      if (hidden) hidden.value = this.checked;
      updateQualityDisplay();
    });
  }

  console.log('Обработчики качества инициализированы');
}

/**
 * Добавляет тестовую кнопку для отладки геометрии
 */
function addDebugButton() {
  const debugBtn = document.createElement('button');
  debugBtn.textContent = 'Debug Geometry';
  debugBtn.type = 'button';
  debugBtn.className = 'debug-geometry-btn';
  debugBtn.style.position = 'fixed';
  debugBtn.style.top = '10px';
  debugBtn.style.right = '10px';
  debugBtn.style.zIndex = '10000';
  debugBtn.style.padding = '5px 10px';
  debugBtn.style.fontSize = '12px';
  debugBtn.onclick = function () {
    const geometryInput = document.getElementById('geometry');
    console.log('=== DEBUG GEOMETRY ===');
    console.log('Поле найдено:', geometryInput ? 'ДА' : 'НЕТ');
    if (geometryInput) {
      console.log('Значение:', geometryInput.value);
      console.log('Длина:', geometryInput.value.length);
    }
    console.log('drawnItems слои:', drawnItems ? drawnItems.getLayers().length : 'нет drawnItems');
  };
  document.body.appendChild(debugBtn);
}

/**
 * Основная функция инициализации страницы
 */
async function initAddBikeLanePage() {
  console.log('Начало инициализации страницы');

  await loadCitiesData();

  initMap();
  initPhotoHandlers();
  initFormValidation();
  initInteractiveElements();
  initQualityHandlers();

  addDebugButton();

  console.log('Инициализация страницы завершена');
}

// Инициализация после загрузки страницы
document.addEventListener('DOMContentLoaded', function () {
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
          <button class="button_square_label btn_blue" id="success-add-more">
            Добавить еще одну
          </button>
          <button class="button_square_label btn_outline" id="success-close">
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

  const addMoreBtn = modal.querySelector('#success-add-more');
  const closeBtn = modal.querySelector('#success-close');

  if (addMoreBtn) addMoreBtn.addEventListener('click', () => location.reload());
  if (closeBtn) closeBtn.addEventListener('click', closeSuccessModal);

  modal.addEventListener('click', function (e) {
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
