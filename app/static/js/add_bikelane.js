// Скрипт для страницы добавления велодорожки

// Глобальные переменные для карты
let map, drawnItems, drawControl, currentPolyline, citiesData;
let isMobileMapLayout = false;
let isDrawingLine = false;
let currentLinePoints = [];
let drawingPointMarkers = [];
let isSubmittingBikelaneForm = false;
let selectedPhotoFiles = [];
let photoPreviewRenderId = 0;
let shouldShowValidationErrors = false;

function isBusLaneSelected() {
  return document.querySelector('input[name="track_type"]:checked')?.value === 'bus_lane';
}

function updateTrackTypeFormMode() {
  const form = document.getElementById('bikelane-form');
  const title = document.getElementById('title');
  const isBusLane = isBusLaneSelected();

  if (form) {
    form.classList.toggle('is-bus-lane', isBusLane);
    form.querySelectorAll('.bikelane-only').forEach((section) => {
      section.hidden = isBusLane;
      section.setAttribute('aria-hidden', isBusLane ? 'true' : 'false');
      section.querySelectorAll('input, textarea, select').forEach((field) => {
        field.disabled = isBusLane;
      });
    });
  }
  if (title) {
    title.placeholder = isBusLane ? 'Название улицы' : 'Название или адрес';
  }

  updateDescriptionCounter();
  updateSubmitButtonState();
}

function getDescriptionMinLength() {
  const form = document.getElementById('bikelane-form');
  const configured = Number.parseInt(form?.dataset.descriptionMinLength || '20', 10);
  return Number.isFinite(configured) && configured >= 1 ? configured : 20;
}

function updateDescriptionCounter() {
  const description = document.getElementById('description');
  const counter = document.getElementById('description-counter');

  if (!description || !counter) {
    return;
  }

  const length = description.value.trim().length;
  const minLength = getDescriptionMinLength();
  counter.textContent = String(length);
  counter.classList.toggle('is-short', length > 0 && length < minLength);
  counter.classList.toggle('is-valid', length >= minLength);
}

function initDescriptionCounter() {
  const description = document.getElementById('description');

  if (!description) {
    return;
  }

  description.removeAttribute('minlength');
  description.required = false;
  description.addEventListener('input', updateDescriptionCounter);
  description.addEventListener('change', updateDescriptionCounter);
  updateDescriptionCounter();
}

function showToast(message, type = 'info', options = {}) {
  const container = document.getElementById('toast-container');
  if (!container || !message) {
    return;
  }

  const duration = options.duration ?? 4000;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
  toast.innerHTML = `
    <p class="toast-message"></p>
  `;

  const messageElement = toast.querySelector('.toast-message');
  if (messageElement) {
    messageElement.textContent = message;
  }

  const removeToast = () => {
    toast.style.animation = 'toast-out 0.2s ease forwards';
    window.setTimeout(() => toast.remove(), 180);
  };

  container.appendChild(toast);
  window.setTimeout(removeToast, duration);
}

function getFormValidationErrors() {
  const city = document.getElementById('city')?.value || '';
  const title = document.getElementById('title')?.value.trim() || '';
  const description = document.getElementById('description')?.value.trim() || '';
  const trackType = document.querySelector('input[name="track_type"]:checked');
  const isBusLane = trackType?.value === 'bus_lane';
  const geometry = document.getElementById('geometry')?.value || '';
  const errors = [];

  if (!city) errors.push('Необходимо выбрать город');
  if (title.length < 3) errors.push('Название должно содержать минимум 3 символа');
  if (!isBusLane && description.length < getDescriptionMinLength()) {
    errors.push(`Описание должно содержать минимум ${getDescriptionMinLength()} символов`);
  }
  if (!trackType) errors.push('Необходимо выбрать тип дорожки');

  if (!geometry || geometry.trim() === '') {
    errors.push('Необходимо нарисовать линию на карте');
  } else {
    try {
      const parsed = JSON.parse(geometry);
      if (!parsed.coordinates || parsed.coordinates.length < 2) {
        errors.push('Линия должна содержать минимум 2 точки');
      } else if (calculateLineDistance(parsed.coordinates) < 10) {
        errors.push('Велодорожка должна быть длиннее 10 метров');
      }
    } catch (error) {
      errors.push('Ошибка в данных геометрии');
    }
  }

  return errors;
}

function getFirstInvalidFormElement() {
  const city = document.getElementById('city');
  if (city && !city.value) return city;

  const title = document.getElementById('title');
  if (title && title.value.trim().length < 3) return title;

  const description = document.getElementById('description');
  if (
    !isBusLaneSelected()
    && description
    && description.value.trim().length < getDescriptionMinLength()
  ) return description;

  const trackType = document.querySelector('input[name="track_type"]:checked');
  if (!trackType) return document.querySelector('.track-types') || document.querySelector('input[name="track_type"]');

  const geometry = document.getElementById('geometry')?.value || '';
  if (!geometry || geometry.trim() === '') {
    return document.getElementById('map-section') || document.getElementById('open-map-drawer-btn');
  }

  try {
    const parsed = JSON.parse(geometry);
    if (!parsed.coordinates || parsed.coordinates.length < 2 || calculateLineDistance(parsed.coordinates) < 10) {
      return document.getElementById('map-section') || document.getElementById('open-map-drawer-btn');
    }
  } catch (error) {
    return document.getElementById('map-section') || document.getElementById('open-map-drawer-btn');
  }

  return null;
}

function setElementError(element, hasError) {
  if (!element) {
    return;
  }

  element.classList.toggle('error', hasError);
}

function updateFormErrorClasses() {
  const city = document.getElementById('city');
  const title = document.getElementById('title');
  const trackTypeInputs = document.querySelectorAll('input[name="track_type"]');
  const trackTypes = document.querySelector('.track-types');
  const mapSection = document.getElementById('map-section');
  const geometry = document.getElementById('geometry')?.value || '';

  setElementError(city, Boolean(city && !city.value));
  setElementError(title, Boolean(title && title.value.trim().length < 3));

  const hasTrackType = Boolean(document.querySelector('input[name="track_type"]:checked'));
  trackTypeInputs.forEach((input) => setElementError(input, !hasTrackType));
  setElementError(trackTypes, !hasTrackType);

  let hasGeometryError = !geometry || geometry.trim() === '';
  if (!hasGeometryError) {
    try {
      const parsed = JSON.parse(geometry);
      hasGeometryError =
        !parsed.coordinates ||
        parsed.coordinates.length < 2 ||
        calculateLineDistance(parsed.coordinates) < 10;
    } catch (error) {
      hasGeometryError = true;
    }
  }

  setElementError(mapSection, hasGeometryError);
}

function clearFormErrorClasses() {
  document
    .querySelectorAll('#bikelane-form .error')
    .forEach((element) => element.classList.remove('error'));
}

function scrollToRequiredFormElement(element) {
  if (!element) {
    return;
  }

  element.scrollIntoView({ behavior: 'smooth', block: 'center' });

  if (typeof element.focus === 'function' && !element.matches?.('.track-types, .island')) {
    window.setTimeout(() => element.focus({ preventScroll: true }), 350);
  }
}

function showDisabledSubmitFeedback() {
  const errors = getFormValidationErrors();
  if (errors.length === 0) {
    return;
  }

  shouldShowValidationErrors = true;
  updateFormErrorClasses();
  showToast('Заполните обязательные поля, чтобы отправить велодорожку', 'error', { duration: 5000 });
  scrollToRequiredFormElement(getFirstInvalidFormElement());
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function getRewardConfig() {
  return window.bikelaneRewardConfig || {
    maxScore: 0,
    checkpoints: [],
    rules: []
  };
}

function getValidGeometryDistance(form) {
  const geometry = form.querySelector('#geometry')?.value?.trim();
  if (!geometry) {
    return 0;
  }

  try {
    const parsed = JSON.parse(geometry);
    if (!parsed.coordinates || parsed.coordinates.length < 2) {
      return 0;
    }
    return calculateLineDistance(parsed.coordinates);
  } catch (error) {
    return 0;
  }
}

function getRewardRuleScore(rule, form) {
  const points = Number(rule.points || 0);
  const maxItems = Number(rule.maxItems || 1);

  if (!points || maxItems <= 0) {
    return 0;
  }

  if (
    isBusLaneSelected()
    && ['description', 'quality', 'video'].includes(rule.id)
  ) {
    return 0;
  }

  if (rule.id === 'base_submission') {
    return getValidGeometryDistance(form) >= 10 ? points : 0;
  }

  if (rule.id === 'photos') {
    const photosInput = form.querySelector('#photos');
    const selectedCount = photosInput?.files?.length || selectedPhotoFiles.length || 0;
    const previewCount = document.querySelector('#photos-preview')?.children.length || 0;
    return Math.min(Math.max(selectedCount, previewCount), maxItems) * points;
  }

  if (rule.id === 'video') {
    const videoUrl = form.querySelector('input[name="video_url"]')?.value?.trim() || '';
    return videoUrl ? points * Math.min(maxItems, 1) : 0;
  }

  const fields = Array.isArray(rule.fields) ? rule.fields : [];
  const minLength = Number(rule.minLength || 0);
  if (!fields.length) {
    return 0;
  }

  const isComplete = fields.every((fieldName) => {
    const field = form.querySelector(`#${fieldName}, [name="${fieldName}"]`);
    if (!field) {
      return false;
    }
    if (field.type === 'radio') {
      return Boolean(form.querySelector(`input[name="${field.name}"]:checked`));
    }
    if (field.type === 'checkbox') {
      return field.checked;
    }

    const value = field.value?.trim() || '';
    if (minLength > 0) {
      return value.length >= minLength;
    }
    return Boolean(value);
  });

  return isComplete ? points : 0;
}

function calculateCurrentRewardState(form, config) {
  const rules = Array.isArray(config.rules) ? config.rules : [];
  const score = rules.reduce((sum, rule) => sum + getRewardRuleScore(rule, form), 0);
  const maxScore = Number(config.maxScore || score || 0);

  return {
    score: maxScore ? Math.min(score, maxScore) : score,
    maxScore,
    checkpoints: Array.isArray(config.checkpoints) ? config.checkpoints : []
  };
}

function createSubmitScoreSegment(progressValue) {
  const segment = document.createElement('span');
  const fill = document.createElement('span');

  segment.className = 'submit-score__segment';
  fill.className = 'submit-score__segment-fill';
  fill.style.setProperty('--segment-progress', String(clamp(progressValue, 0, 1)));

  segment.appendChild(fill);
  return segment;
}

function createSubmitScoreBadge(checkpoint, score) {
  const badge = document.createElement('span');
  const coin = document.createElement('img');
  const label = document.createElement('span');

  badge.className = 'submit-score__badge';
  badge.classList.toggle('is-active', score >= checkpoint);
  badge.dataset.scoreBadge = String(checkpoint);

  coin.className = 'submit-score__coin';
  coin.src = '/static/img/icon/coin.png';
  coin.alt = '';
  coin.setAttribute('aria-hidden', 'true');

  label.textContent = String(checkpoint);

  badge.appendChild(coin);
  badge.appendChild(label);
  return badge;
}

function renderSubmitScoreProgress(state) {
  const progress = document.querySelector('#submit-score-progress');
  if (!progress) {
    return;
  }

  const checkpoints = state.checkpoints
    .map((value) => Number(value))
    .filter((value) => value > 0);
  const allPoints = [0, ...checkpoints];

  progress.innerHTML = '';

  checkpoints.forEach((checkpoint, index) => {
    const from = allPoints[index];
    const segmentProgress = checkpoint > from ? (state.score - from) / (checkpoint - from) : 0;

    progress.appendChild(createSubmitScoreSegment(segmentProgress));
    progress.appendChild(createSubmitScoreBadge(checkpoint, state.score));
  });

  progress.setAttribute(
    'aria-label',
    `Прогресс заполнения формы: ${Math.round(state.score)} из ${Math.round(state.maxScore)} баллов`
  );
}

function updateSubmitScoreProgress() {
  const form = document.querySelector('#bikelane-form');
  if (!form) {
    return;
  }

  const config = getRewardConfig();
  const state = calculateCurrentRewardState(form, config);
  renderSubmitScoreProgress(state);
}

window.updateSubmitScoreProgress = updateSubmitScoreProgress;

function updateSubmitButtonState() {
  const submitButton = document.getElementById('submit-bikelane-btn');
  if (!submitButton) {
    return;
  }

  if (isSubmittingBikelaneForm) {
    submitButton.disabled = true;
    return;
  }

  submitButton.disabled = getFormValidationErrors().length > 0;

  if (shouldShowValidationErrors) {
    updateFormErrorClasses();
  } else {
    clearFormErrorClasses();
  }

  updateSubmitScoreProgress();
}

function getSubmitButtonDefaultLabel() {
  return document.getElementById('submit-bikelane-btn')?.dataset.defaultLabel || 'Отправить';
}

function isMobileViewport() {
  return window.matchMedia('(max-width: 768px)').matches;
}

function syncMapDrawerLayout() {
  const inlineAnchor = document.getElementById('map-inline-anchor');
  const drawerBody = document.getElementById('map-drawer-body');
  const content = document.getElementById('map-drawer-content');

  if (!inlineAnchor || !drawerBody || !content) {
    return;
  }

  const shouldUseDrawer = isMobileViewport();
  const targetParent = shouldUseDrawer ? drawerBody : inlineAnchor;

  if (content.parentElement !== targetParent) {
    targetParent.appendChild(content);
  }

  isMobileMapLayout = shouldUseDrawer;
}

function openMapDrawer() {
  if (!isMobileViewport()) {
    return;
  }

  const drawer = document.getElementById('map-drawer');
  if (!drawer) {
    return;
  }

  syncMapDrawerLayout();
  drawer.classList.add('is-open');
  drawer.setAttribute('aria-hidden', 'false');
  document.body.classList.add('map-drawer-open');

  setTimeout(() => {
    if (map) {
      map.invalidateSize();
      if (currentPolyline) {
        map.fitBounds(currentPolyline.getBounds(), {
          padding: [24, 24],
          maxZoom: 17
        });
      }
    }
  }, 260);
}

function closeMapDrawer() {
  const drawer = document.getElementById('map-drawer');
  if (!drawer) {
    return;
  }

  drawer.classList.remove('is-open');
  drawer.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('map-drawer-open');
}

function initMapDrawer() {
  const openBtn = document.getElementById('open-map-drawer-btn');
  const closeBtn = document.getElementById('close-map-drawer-btn');
  const overlay = document.getElementById('map-drawer-overlay');

  syncMapDrawerLayout();

  if (openBtn) {
    openBtn.addEventListener('click', openMapDrawer);
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', closeMapDrawer);
  }

  if (overlay) {
    overlay.addEventListener('click', closeMapDrawer);
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      closeMapDrawer();
    }
  });

  window.addEventListener('resize', function () {
    const wasMobile = isMobileMapLayout;
    syncMapDrawerLayout();

    if (map) {
      setTimeout(() => map.invalidateSize(), 50);
    }

    if (wasMobile && !isMobileViewport()) {
      closeMapDrawer();
    }
  });
}

/**
 * Загрузка данных о городах и заполнение селекта
 */
async function loadCitiesData() {
  try {
    if (window.citiesDataFromServer?.cities?.length) {
      citiesData = window.citiesDataFromServer;
      console.log('Города загружены с сервера:', citiesData.cities.length);
      populateCitySelect();
      return;
    }

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
 * Заполняет селект городов
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

  const selectedCity = citySelect.dataset.selectedCity;
  if (selectedCity) {
    citySelect.value = selectedCity;
  }

  console.log(`Селект заполнен: ${citiesData.cities.length} городов`);
}

function toggleMapSectionVisibility(selectedCity) {
  const mapSection = document.getElementById('map-section');
  if (!mapSection) {
    return;
  }

  const hasSelectedCity = Boolean(selectedCity);
  mapSection.classList.toggle('hidden', !hasSelectedCity);

  if (hasSelectedCity && map) {
    window.setTimeout(() => map.invalidateSize(), 50);
  }
}

function focusMapOnSelectedCity(selectedCity) {
  if (!selectedCity || !citiesData || !map) {
    return;
  }

  const city = citiesData.cities.find((item) => item.id === selectedCity);
  if (!city) {
    console.log('Данные города не найдены');
    return;
  }

  map.setView(city.coords, city.zoom || 12);
  console.log('Карта перемещена к городу:', city.name);
}

function applySelectedCityState(selectedCity) {
  toggleMapSectionVisibility(selectedCity);
  focusMapOnSelectedCity(selectedCity);
  updateAddObjectTabCities(selectedCity);
}

function updateAddObjectTabCities(selectedCity) {
  document.querySelectorAll('[data-add-object-type]').forEach((tab) => {
    const type = tab.dataset.addObjectType;
    const url = new URL('/add-bikelane', window.location.origin);
    if (type && type !== 'bikelane') {
      url.searchParams.set('type', type);
    }
    if (selectedCity) {
      url.searchParams.set('city', selectedCity);
    }
    tab.href = `${url.pathname}${url.search}`;
  });
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
  if (trackType === 'bus_lane') {
    return null;
  }

  const qualityInput = document.querySelector('input[name="quality"]:checked');
  const surfaceQuality = qualityInput ? parseInt(qualityInput.value) : 3;
  if (!qualityInput) {
    console.log('Качество покрытия не выбрано, используется нейтральная оценка');
  }

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
    quality -= 2;
    console.log('Паркуются авто: -2 балла');
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

function getQualityStarsColor(quality) {
  if (isBusLaneSelected() || quality === null) {
    return '#3498db';
  }
  return {
    1: '#e74c3c',
    2: '#e67e22',
    3: '#f39c12',
    4: '#2ecc71',
    5: '#27ae60'
  }[quality] || '#3498db';
}

function updateCurrentPolylineColor(quality = calculateOverallQuality()) {
  currentPolyline?.setStyle({
    color: getQualityStarsColor(quality)
  });
}

/**
 * Обновляет отображение качества велодорожки
 */
function updateQualityDisplay() {
  const quality = calculateOverallQuality();

  const section = document.getElementById('quality-display-section');
  if (quality === null) {
    if (section) section.style.display = 'none';
    updateCurrentPolylineColor(null);
    return;
  }
  if (section) section.style.display = 'block';
  updateCurrentPolylineColor(quality);

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

function clearDistanceField() {
  const distanceInput = document.getElementById('distance');
  if (distanceInput) {
    distanceInput.value = '';
  }
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
function getCurrentLineCoordinates() {
  const points = isDrawingLine
    ? currentLinePoints
    : (currentPolyline?.getLatLngs?.() || []);
  return points.map((point) => [point.lng, point.lat]);
}

function updateMapEditorUi() {
  const state = document.getElementById('map-editor-state');
  const meta = document.getElementById('map-editor-meta');
  const drawerSubtitle = document.getElementById('map-drawer-subtitle');
  const triggerLabel = document.getElementById('open-map-drawer-label');
  const finishBtn = document.getElementById('finish-line-btn');
  const undoBtn = document.getElementById('undo-line-point-btn');
  const resetBtn = document.getElementById('reset-line-btn');
  const mapContainer = document.getElementById('map-container');
  const coordinates = getCurrentLineCoordinates();
  const pointCount = coordinates.length;
  const distance = calculateLineDistance(coordinates);
  const hasLine = Boolean(currentPolyline && pointCount);

  mapContainer?.classList.toggle('is-drawing', isDrawingLine);
  if (undoBtn) undoBtn.disabled = !isDrawingLine || pointCount === 0;
  if (finishBtn) finishBtn.disabled = !isDrawingLine || pointCount < 2;
  if (resetBtn) resetBtn.disabled = !hasLine;

  state?.classList.toggle('is-drawing', isDrawingLine);
  state?.classList.toggle('is-ready', hasLine && !isDrawingLine);

  if (isDrawingLine) {
    if (state) state.textContent = 'Рисование линии';
    const instruction = pointCount < 2
      ? 'Добавьте ещё минимум одну точку'
      : `${pointCount} точек • ${formatDistance(distance)} • Нажмите «Готово»`;
    if (meta) meta.textContent = instruction;
    if (drawerSubtitle) drawerSubtitle.textContent = instruction;
    if (triggerLabel) triggerLabel.textContent = `Продолжить рисование • ${pointCount} точек`;
    return;
  }

  if (hasLine) {
    if (state) state.textContent = 'Линия готова';
    const details = `${pointCount} точек • ${formatDistance(distance)} • Точки можно перетаскивать`;
    if (meta) meta.textContent = details;
    if (drawerSubtitle) drawerSubtitle.textContent = 'Перетаскивайте точки для точной корректировки линии.';
    if (triggerLabel) triggerLabel.textContent = `Изменить линию • ${formatDistance(distance)}`;
    return;
  }

  if (state) state.textContent = 'Линия не добавлена';
  if (meta) meta.textContent = 'Нажмите на карту, чтобы поставить первую точку';
  if (drawerSubtitle) drawerSubtitle.textContent = 'Нажмите на карту, чтобы поставить первую точку.';
  if (triggerLabel) triggerLabel.textContent = 'Открыть карту для рисования';
}

function bindPolylineEditing(polyline) {
  currentPolyline = polyline;
  if (polyline.editing) {
    polyline.editing.enable();
  }
  if (polyline._velojolEditHandlerBound) {
    return;
  }
  polyline._velojolEditHandlerBound = true;
  polyline.on('edit', function () {
    updateGeometryFromMap();
    updateGeometryStatus('Изменения линии сохранены в форме', 'valid');
    updateMapEditorUi();
  });
}

function clearCurrentLine() {
  drawnItems?.clearLayers();
  currentLinePoints = [];
  drawingPointMarkers = [];
  currentPolyline = null;
  isDrawingLine = false;

  const geometryInput = document.getElementById('geometry');
  if (geometryInput) geometryInput.value = '';

  const distanceElement = document.getElementById('distance-display');
  if (distanceElement) distanceElement.style.display = 'none';

  clearDistanceField();
  updateSubmitButtonState();
  updateMapEditorUi();
}

function addDrawingPointMarker(latlng) {
  const marker = L.circleMarker(latlng, {
    radius: isMobileViewport() ? 7 : 6,
    color: '#fefefe',
    weight: 3,
    fillColor: '#3498db',
    fillOpacity: 1,
    interactive: false
  }).addTo(drawnItems);
  drawingPointMarkers.push(marker);
}

function startNewLine(latlng) {
  clearCurrentLine();
  currentLinePoints = [latlng];
  currentPolyline = L.polyline(currentLinePoints, {
    color: getQualityStarsColor(calculateOverallQuality()),
    weight: 5,
    opacity: 0.9
  }).addTo(drawnItems);
  addDrawingPointMarker(latlng);
  isDrawingLine = true;
  updateGeometryStatus(
    'Добавляйте точки по ходу линии. Ошибочную точку можно отменить.',
    'info'
  );
  updateMapEditorUi();
}

function addPointToLine(latlng) {
  currentLinePoints.push(latlng);
  currentPolyline.setLatLngs(currentLinePoints);
  addDrawingPointMarker(latlng);
  updateMapEditorUi();
}

function undoLastLinePoint() {
  if (!isDrawingLine || currentLinePoints.length === 0) {
    return;
  }

  currentLinePoints.pop();
  const removedMarker = drawingPointMarkers.pop();
  if (removedMarker) {
    drawnItems.removeLayer(removedMarker);
  }
  if (currentLinePoints.length === 0) {
    clearCurrentLine();
    updateGeometryStatus('Нажмите на карту, чтобы поставить первую точку', 'info');
    return;
  }

  currentPolyline.setLatLngs(currentLinePoints);
  updateMapEditorUi();
}

function resetLine() {
  const coordinates = getCurrentLineCoordinates();
  if (
    coordinates.length >= 2
    && !window.confirm('Очистить текущую линию и нарисовать заново?')
  ) {
    return;
  }

  clearCurrentLine();
  updateGeometryStatus('Нажмите на карту, чтобы поставить первую точку', 'info');
}

function finishLine() {
  if (!isDrawingLine || currentLinePoints.length < 2) {
    updateGeometryStatus('Линия должна содержать минимум 2 точки', 'invalid');
    return;
  }

  isDrawingLine = false;
  const coordinates = getCurrentLineCoordinates();
  const geojson = {
    type: 'LineString',
    coordinates
  };
  const distance = updateDistanceDisplay(coordinates);
  addDistanceField(distance);

  const geometryInput = document.getElementById('geometry');
  if (!geometryInput) {
    return;
  }
  geometryInput.value = JSON.stringify(geojson);
  drawingPointMarkers.forEach((marker) => drawnItems.removeLayer(marker));
  drawingPointMarkers = [];
  bindPolylineEditing(currentPolyline);
  updateSubmitButtonState();
  validateGeometry();
  updateGeometryStatus(
    `Линия готова. Дистанция: ${formatDistance(distance)}. Перетаскивайте точки для корректировки.`,
    'valid'
  );
  updateMapEditorUi();

  if (isMobileViewport()) {
    closeMapDrawer();
  }
}

function initDrawingHandlers() {
  console.log('Инициализация обработчиков рисования');

  const finishBtn = document.getElementById('finish-line-btn');
  const undoBtn = document.getElementById('undo-line-point-btn');
  const resetBtn = document.getElementById('reset-line-btn');

  map.on('click', function (event) {
    if (!isDrawingLine && currentPolyline) {
      updateGeometryStatus(
        'Линия уже готова. Перетаскивайте точки или нажмите «Заново».',
        'info'
      );
      return;
    }
    if (isDrawingLine) {
      addPointToLine(event.latlng);
    } else {
      startNewLine(event.latlng);
    }
  });

  finishBtn?.addEventListener('click', finishLine);
  undoBtn?.addEventListener('click', undoLastLinePoint);
  resetBtn?.addEventListener('click', resetLine);

  document.addEventListener('keydown', function (event) {
    const target = event.target;
    const isTextField = target?.matches?.('input, textarea, select');
    if (
      isDrawingLine
      && !isTextField
      && (event.metaKey || event.ctrlKey)
      && event.key.toLowerCase() === 'z'
    ) {
      event.preventDefault();
      undoLastLinePoint();
    }
  });

  updateMapEditorUi();
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
          color: getQualityStarsColor(calculateOverallQuality()),
          weight: 5,
          opacity: 0.9
        }).addTo(drawnItems);

        bindPolylineEditing(polyline);

        map.fitBounds(polyline.getBounds());

        const distance = updateDistanceDisplay(geojson.coordinates);
        addDistanceField(distance);

        updateGeometryStatus('Линия загружена из сохраненных данных', 'valid');
        updateSubmitButtonState();
        updateMapEditorUi();
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
    updateSubmitButtonState();
    return false;
  }

  try {
    const geojson = JSON.parse(geometryValue);
    if (geojson.type === 'LineString' && geojson.coordinates && geojson.coordinates.length >= 2) {
      updateGeometryStatus('✓ Геометрия корректна', 'valid');
      updateSubmitButtonState();
      return true;
    } else {
      updateGeometryStatus('✗ Некорректная геометрия', 'invalid');
      updateSubmitButtonState();
      return false;
    }
  } catch (e) {
    updateGeometryStatus('✗ Ошибка в данных геометрии', 'invalid');
    updateSubmitButtonState();
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
      updateSubmitButtonState();

      const distance = updateDistanceDisplay(coordinates);
      addDistanceField(distance);
      updateMapEditorUi();

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

  if (files.length === 0) {
    console.log('Файлы не выбраны');
    return;
  }

  const imageFiles = files.filter((file) => file.type.startsWith('image/'));
  const skippedFiles = files.length - imageFiles.length;

  if (skippedFiles > 0) {
    console.log('Пропущено не-изображений:', skippedFiles);
  }

  if (selectedPhotoFiles.length + imageFiles.length > 10) {
    showToast('Максимум 10 фотографий', 'error');
    syncPhotoInputFiles(fileInput);
    return;
  }

  selectedPhotoFiles = selectedPhotoFiles.concat(imageFiles);
  syncPhotoInputFiles(fileInput);
  renderPhotoPreviews(fileInput, preview);
  updateSubmitScoreProgress();
}

function syncPhotoInputFiles(fileInput) {
  const dt = new DataTransfer();
  selectedPhotoFiles.forEach((file) => dt.items.add(file));
  fileInput.files = dt.files;
}

function renderPhotoPreviews(fileInput, preview) {
  photoPreviewRenderId++;
  const currentRenderId = photoPreviewRenderId;
  preview.innerHTML = '';

  selectedPhotoFiles.forEach((file, index) => {
    console.log(`Файл ${index + 1}:`, file.name, 'Тип:', file.type, 'Размер:', file.size);

    const reader = new FileReader();

    reader.onload = function (e) {
      if (currentRenderId !== photoPreviewRenderId) {
        return;
      }

      console.log(`Файл ${index + 1} загружен в FileReader`);

      const photoDiv = document.createElement('div');
      photoDiv.className = 'photo-preview';
      photoDiv.innerHTML = `
        <img src="${e.target.result}" alt="Фото ${index + 1}">
        <button type="button" class="photo-preview-remove" aria-label="Удалить фото">
          <img src="/static/img/icon/cross.svg" alt="">
        </button>
      `;

      const removeButton = photoDiv.querySelector('.photo-preview-remove');
      removeButton.addEventListener('click', function () {
        selectedPhotoFiles.splice(index, 1);
        syncPhotoInputFiles(fileInput);
        renderPhotoPreviews(fileInput, preview);
        updateSubmitScoreProgress();
      });

      preview.appendChild(photoDiv);
      console.log(`Фото ${index + 1} добавлено в превью`);
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

  const submitBtn = document.getElementById('submit-bikelane-btn');
  const fieldsToWatch = form.querySelectorAll(
    '#city, #title, #description, input[name="track_type"], input[name="quality"]'
  );

  fieldsToWatch.forEach((field) => {
    const primaryEvent = field.matches('input[type="radio"], select') ? 'change' : 'input';
    field.addEventListener(primaryEvent, updateSubmitButtonState);
    if (primaryEvent !== 'change') {
      field.addEventListener('change', updateSubmitButtonState);
    }
  });

  form.addEventListener('input', updateSubmitScoreProgress);
  form.addEventListener('change', updateSubmitScoreProgress);
  updateSubmitButtonState();

  if (submitBtn) {
    let lastDisabledFeedbackAt = 0;
    const handleDisabledPress = function () {
      if (submitBtn.disabled) {
        const now = Date.now();
        if (now - lastDisabledFeedbackAt < 500) {
          return;
        }
        lastDisabledFeedbackAt = now;
        showDisabledSubmitFeedback();
      }
    };

    submitBtn.addEventListener('pointerdown', handleDisabledPress);
    submitBtn.addEventListener('touchstart', handleDisabledPress, { passive: true });

    const submitSection = submitBtn.closest('.submit-section');
    if (submitSection) {
      submitSection.addEventListener('pointerdown', function (event) {
        if (event.target === submitSection || event.target === submitBtn) {
          handleDisabledPress();
        }
      });
    }
  }

  form.addEventListener('submit', function (e) {
    console.log('=== ВАЛИДАЦИЯ ФОРМЫ ===');
    const errors = getFormValidationErrors();

    console.log('Результат валидации:', errors.length === 0 ? 'ВСЕ ОК' : 'ЕСТЬ ОШИБКИ');
    console.log('Ошибки:', errors);

    if (errors.length > 0) {
      e.preventDefault();
      shouldShowValidationErrors = true;
      updateFormErrorClasses();
      showToast(errors.join('\n'), 'error', { duration: 5000 });
      updateSubmitButtonState();
      return false;
    }

    // Показываем индикатор загрузки
    if (submitBtn) {
      isSubmittingBikelaneForm = true;
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
          selectedPhotoFiles = [];
          const photosInput = document.getElementById('photos');
          if (photosInput) {
            syncPhotoInputFiles(photosInput);
          }
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
          clearDistanceField();

          updateSubmitButtonState();
        } else {
          console.log('Сервер вернул ошибку:', data.error);
          showToast('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
      })
      .catch((error) => {
        console.error('Ошибка отправки:', error);
        showToast('Ошибка при отправке формы: ' + error.message, 'error');
      })
      .finally(() => {
        // Восстанавливаем кнопку
        isSubmittingBikelaneForm = false;
        if (submitBtn) {
          submitBtn.textContent = getSubmitButtonDefaultLabel();
          updateSubmitButtonState();
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
    applySelectedCityState(citySelect.value);

    citySelect.addEventListener('change', function () {
      const selectedCity = this.value;
      console.log('Выбран город:', selectedCity);
      applySelectedCityState(selectedCity);
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
      updateTrackTypeFormMode();
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

  const oneWayToggle = document.getElementById('is_one_way');
  if (oneWayToggle) {
    oneWayToggle.addEventListener('change', function () {
      console.log('Изменена односторонность:', this.checked);
      const hidden = document.getElementById('is_one_way_hidden');
      if (hidden) hidden.value = this.checked;
    });
  }

  console.log('Обработчики качества инициализированы');
}

function syncExistingToggleState() {
  const toggleMappings = [
    ['has_parking', 'has_parking_hidden'],
    ['has_markings', 'has_markings_hidden'],
    ['has_signs', 'has_signs_hidden'],
    ['is_one_way', 'is_one_way_hidden']
  ];

  toggleMappings.forEach(([checkboxId, hiddenId]) => {
    const checkbox = document.getElementById(checkboxId);
    const hidden = document.getElementById(hiddenId);
    if (checkbox && hidden) {
      hidden.value = checkbox.checked ? 'true' : 'false';
    }
  });
}

function getCityPageUrl(data = {}) {
  const cityId = data.city || document.getElementById('city')?.value || '';

  if (!cityId) {
    return null;
  }

  return `/city/${encodeURIComponent(cityId)}`;
}

/**
 * Основная функция инициализации страницы
 */
async function initAddBikeLanePage() {
  console.log('Начало инициализации страницы');

  initDescriptionCounter();
  initQualityHandlers();
  updateTrackTypeFormMode();

  await loadCitiesData();

  initMapDrawer();
  initMap();
  initPhotoHandlers();
  initFormValidation();
  initInteractiveElements();
  syncExistingToggleState();
  updateQualityDisplay();

  updateSubmitButtonState();

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
  const title = data.modal_title || 'Велодорожка отправлена!';
  const message =
    data.modal_message ||
    'Спасибо за ваш вклад в развитие велоинфраструктуры! Велодорожка будет проверена модераторами в течение 1-2 рабочих дней.';
  const primaryLabel = data.primary_action_label || 'Добавить еще одну';
  const closeLabel = data.close_action_label || 'Закрыть';
  const redirectUrl = data.redirect_url || null;
  const cityPageUrl = getCityPageUrl(data);

  const modal = document.createElement('div');
  modal.className = 'success-modal-overlay';
  modal.innerHTML = `
    <div class="success-modal">
      <div class="success-modal-content">
        <div class="success-icon">

         <!--Todo: заменить  иконку галочки-->
          <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22,4 12,14.01 9,11.01"></polyline>
          </svg>
        </div>

        <h2>${title}</h2>

        <p>${message}</p>

        <div class="success-actions">
          <button class="button__label btn_blue" id="success-add-more">
            ${primaryLabel}
          </button>
          <button class="button__label btn_outline" id="success-close">
            ${closeLabel}
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
        background: white; border-radius: var(--spacer-m); padding: 2rem;
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

  if (addMoreBtn) {
    addMoreBtn.addEventListener('click', () => {
      if (redirectUrl) {
        window.location.href = redirectUrl;
        return;
      }
      location.reload();
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      if (cityPageUrl) {
        window.location.href = cityPageUrl;
        return;
      }
      if (redirectUrl) {
        window.location.href = redirectUrl;
        return;
      }
      closeSuccessModal();
    });
  }

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
