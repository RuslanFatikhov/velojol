/**
 * Скрипт для карты города с Mapbox GL JS
 */

const MAPBOX_TOKEN = String(window.MAPBOX_TOKEN || '').trim();

function configureMapbox(containerId) {
    if (!MAPBOX_TOKEN.startsWith('pk.')) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = '<p class="map-config-error">Карта временно недоступна: не настроен публичный токен Mapbox.</p>';
        }
        console.error('Mapbox не настроен: задайте публичный MAPBOX_TOKEN, начинающийся с pk.');
        return false;
    }

    mapboxgl.accessToken = MAPBOX_TOKEN;
    return true;
}

let cityMap;
let bikelaneSourceAdded = false;
let infrastructureMarkers = [];
let userLocationMarker = null;
let photoGalleryState = {
    photos: [],
    currentIndex: 0
};
const CITY_MOBILE_VIEW_STORAGE_KEY = 'cityMobileView';
const CITY_MAP_FILTERS_STORAGE_KEY = 'velojol.cityMap.filters.v1';
const PENDING_USER_LOCATION_STORAGE_KEY = 'velojol.pendingUserLocation.v1';

function isMobileCityView() {
    return window.matchMedia('(max-width: 768px)').matches;
}

function setCityMobileView(view) {
    const container = document.querySelector('.city-container');
    const tabs = document.querySelectorAll('[data-city-view-tab]');

    if (!container) {
        return;
    }

    const nextView = view === 'list' ? 'list' : 'map';
    container.setAttribute('data-city-view', nextView);
    localStorage.setItem(CITY_MOBILE_VIEW_STORAGE_KEY, nextView);

    tabs.forEach((tab) => {
        const isActive = tab.dataset.cityViewTab === nextView;
        tab.classList.toggle('is-active', isActive);
        tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    if (nextView === 'map' && cityMap) {
        setTimeout(() => cityMap.resize(), 50);
    }
}

function initCityMobileTabs() {
    const tabs = document.querySelectorAll('[data-city-view-tab]');

    if (!tabs.length) {
        return;
    }

    tabs.forEach((tab) => {
        tab.addEventListener('click', function() {
            setCityMobileView(this.dataset.cityViewTab);
        });
    });

    if (isMobileCityView()) {
        const savedView = localStorage.getItem(CITY_MOBILE_VIEW_STORAGE_KEY);
        setCityMobileView(savedView || 'map');
    }

    window.addEventListener('resize', function() {
        if (!isMobileCityView()) {
            setCityMobileView('map');
            return;
        }

        const savedView = localStorage.getItem(CITY_MOBILE_VIEW_STORAGE_KEY);
        setCityMobileView(savedView || 'map');
    });
}

function showLocationMessage(message, category = 'info') {
    let container = document.querySelector('.flash-messages');
    if (!container) {
        container = document.createElement('div');
        container.className = 'flash-messages';
        document.body.appendChild(container);
    }

    const item = document.createElement('div');
    item.className = `flash-message flash-${category}`;
    item.textContent = message;
    container.appendChild(item);
    window.setTimeout(() => item.remove(), 5000);
}

function showUserLocation(latitude, longitude) {
    if (!cityMap) {
        return;
    }

    if (userLocationMarker) {
        userLocationMarker.remove();
    }
    userLocationMarker = new mapboxgl.Marker()
        .setLngLat([longitude, latitude])
        .addTo(cityMap);
    cityMap.flyTo({
        center: [longitude, latitude],
        zoom: Math.max(cityMap.getZoom(), 15),
        essential: true
    });
}

function restorePendingUserLocation() {
    let pendingLocation;
    try {
        pendingLocation = JSON.parse(
            sessionStorage.getItem(PENDING_USER_LOCATION_STORAGE_KEY) || 'null'
        );
    } catch (error) {
        sessionStorage.removeItem(PENDING_USER_LOCATION_STORAGE_KEY);
        return;
    }

    if (
        !pendingLocation
        || pendingLocation.cityId !== window.cityData?.id
        || Date.now() - Number(pendingLocation.createdAt) > 5 * 60 * 1000
    ) {
        return;
    }

    sessionStorage.removeItem(PENDING_USER_LOCATION_STORAGE_KEY);
    showUserLocation(
        Number(pendingLocation.latitude),
        Number(pendingLocation.longitude)
    );
}

function collectMapboxCityNames(feature) {
    const properties = feature?.properties || {};
    const place = properties.feature_type === 'place'
        ? properties
        : properties.context?.place;
    const names = [
        properties.name,
        properties.name_preferred,
        place?.name,
    ];

    Object.values(place?.translations || {}).forEach((translation) => {
        names.push(translation?.name);
    });

    return [...new Set(
        names
            .map((name) => String(name || '').trim())
            .filter(Boolean)
    )];
}

async function reverseGeocodeUserCity(latitude, longitude) {
    const url = new URL('https://api.mapbox.com/search/geocode/v6/reverse');
    url.searchParams.set('longitude', longitude);
    url.searchParams.set('latitude', latitude);
    url.searchParams.set('types', 'place');
    url.searchParams.set('language', 'ru,kk,en');
    url.searchParams.set('permanent', 'true');
    url.searchParams.set('access_token', MAPBOX_TOKEN);

    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Mapbox reverse geocoding failed: ${response.status}`);
    }

    const payload = await response.json();
    return collectMapboxCityNames(payload.features?.[0]);
}

function geolocationErrorMessage(error) {
    if (error?.code === 1) {
        return 'Доступ к геолокации запрещён.';
    }
    if (error?.code === 2) {
        return 'Не удалось определить вашу геолокацию.';
    }
    if (error?.code === 3) {
        return 'Определение геолокации заняло слишком много времени.';
    }
    return 'Не удалось определить вашу геолокацию.';
}

function initCityGeolocation() {
    const button = document.getElementById('cityGeolocationButton');
    if (!button) {
        return;
    }

    button.addEventListener('click', function() {
        if (!navigator.geolocation) {
            showLocationMessage(
                'Геолокация не поддерживается этим браузером.',
                'error'
            );
            return;
        }

        button.disabled = true;
        button.setAttribute('aria-busy', 'true');

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;

                try {
                    const cityNames = await reverseGeocodeUserCity(
                        latitude,
                        longitude
                    );
                    const response = await fetch('/api/location/city', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            latitude,
                            longitude,
                            city_names: cityNames
                        })
                    });
                    const payload = await response.json();
                    if (!response.ok || !payload.success) {
                        throw new Error(
                            payload.message || 'Не удалось определить город.'
                        );
                    }

                    if (!payload.available) {
                        showLocationMessage(
                            payload.message || 'Этого города пока нет на сайте.',
                            'info'
                        );
                        return;
                    }

                    if (payload.city.id === window.cityData.id) {
                        showUserLocation(latitude, longitude);
                        return;
                    }

                    sessionStorage.setItem(
                        PENDING_USER_LOCATION_STORAGE_KEY,
                        JSON.stringify({
                            cityId: payload.city.id,
                            latitude,
                            longitude,
                            createdAt: Date.now()
                        })
                    );
                    window.location.assign(payload.redirect_url);
                } catch (error) {
                    console.error('Не удалось обработать геолокацию', error);
                    showLocationMessage(
                        error.message || 'Не удалось определить город.',
                        'error'
                    );
                } finally {
                    button.disabled = false;
                    button.removeAttribute('aria-busy');
                }
            },
            (error) => {
                showLocationMessage(geolocationErrorMessage(error), 'error');
                button.disabled = false;
                button.removeAttribute('aria-busy');
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 60000
            }
        );
    });
}

/**
 * Инициализация карты города
 */
function initCityMap() {
    console.log('Инициализация Mapbox карты...');
    
    if (!document.getElementById('cityMap')) {
        return;
    }

    if (!window.cityData) {
        console.error('Данные города не найдены');
        return;
    }

    if (!configureMapbox('cityMap')) {
        return;
    }
    
    // Создаём карту Mapbox
    cityMap = new mapboxgl.Map({
        container: 'cityMap',
        style: 'mapbox://styles/mapbox/light-v11',
        center: [window.cityData.coords[1], window.cityData.coords[0]], // [lng, lat]
        zoom: window.cityData.zoom - 1 // Mapbox zoom немного отличается
    });
    
    // Добавляем контролы
    cityMap.addControl(new mapboxgl.NavigationControl());
    
    // Когда карта загрузилась, рисуем велодорожки
    cityMap.on('load', function() {
        console.log('Карта загружена');
        drawBikelanes();
        drawInfrastructurePoints();
        applyCurrentFilters();
        restorePendingUserLocation();
    });
    
    console.log('Карта создана');
}

/**
 * Отрисовка велодорожек на карте
 */
function drawBikelanes() {
    if (!window.bikelanesData || window.bikelanesData.length === 0) {
        console.log('Нет велодорожек для отображения');
        return;
    }
    
    console.log(`Отрисовка ${window.bikelanesData.length} велодорожек`);
    
    // Создаём GeoJSON для всех велодорожек
    const geojsonData = {
        type: 'FeatureCollection',
        features: window.bikelanesData.map(bikelane => ({
            type: 'Feature',
            properties: {
                id: bikelane.id,
                title: bikelane.title,
                track_type: bikelane.track_type_display,
                quality: bikelane.quality,
                quality_display: bikelane.quality_display,
                color: bikelane.color || getQualityColor(bikelane.quality)
            },
            geometry: bikelane.geometry
        }))
    };
    
    // Добавляем источник данных
    cityMap.addSource('bikelanes', {
        type: 'geojson',
        data: geojsonData
    });
    
    // Добавляем слой линий
    cityMap.addLayer({
        id: 'bikelanes-layer',
        type: 'line',
        source: 'bikelanes',
        layout: {
            'line-join': 'round',
            'line-cap': 'round'
        },
        paint: {
            'line-color': ['get', 'color'],
            'line-width': 4,
            'line-opacity': 0.8
        }
    });
    
    bikelaneSourceAdded = true;
    
    // Подгоняем карту под все велодорожки
    const coordinates = geojsonData.features.flatMap(f => f.geometry.coordinates);
    if (coordinates.length > 0) {
        const bounds = coordinates.reduce((bounds, coord) => {
            return bounds.extend(coord);
        }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));
        
        cityMap.fitBounds(bounds, { padding: 50 });
    }
    
    // Добавляем обработчик клика
    cityMap.on('click', 'bikelanes-layer', function(e) {
        const bikelaneId = e.features[0].properties.id;
        showBikelaneModal(bikelaneId);
    });
    
    // Меняем курсор при наведении
    cityMap.on('mouseenter', 'bikelanes-layer', function() {
        cityMap.getCanvas().style.cursor = 'pointer';
    });
    
    cityMap.on('mouseleave', 'bikelanes-layer', function() {
        cityMap.getCanvas().style.cursor = '';
    });
    
    console.log('Велодорожки отрисованы');
}

/**
 * Отрисовка велопарковок и ремонтных стоек.
 */
function drawInfrastructurePoints() {
    const points = Array.isArray(window.infrastructureData)
        ? window.infrastructureData
        : [];

    if (!points.length) {
        return;
    }

    infrastructureMarkers = points.map((point) => {
        const markerElement = document.createElement('button');
        const markerIcon = document.createElement('img');
        const iconName = point.type === 'bicycle_repair_station'
            ? 'repair.svg'
            : 'parking.svg';
        markerElement.type = 'button';
        markerElement.className = 'infrastructure-marker';
        markerElement.dataset.infrastructureType = point.type;
        markerElement.setAttribute('aria-label', point.title || point.type_display);
        markerIcon.src = `/static/img/icon/${iconName}`;
        markerIcon.alt = '';
        markerElement.appendChild(markerIcon);

        markerElement.addEventListener('click', function() {
            showInfrastructureModal(point.id);
        });

        const marker = new mapboxgl.Marker({
            element: markerElement,
            anchor: 'bottom'
        })
            .setLngLat(point.coordinates)
            .addTo(cityMap);

        return {
            type: point.type,
            marker,
            element: markerElement
        };
    });

    applyMapLayerFilters();
}

function formatOsmYesNo(value) {
    const normalized = String(value || '').trim().toLowerCase();
    if (['yes', 'true', '1'].includes(normalized)) {
        return 'Да';
    }
    if (['no', 'false', '0'].includes(normalized)) {
        return 'Нет';
    }
    return value;
}

function formatInfrastructureAttributeValue(attribute) {
    if (attribute.value_type === 'yes_no') {
        return formatOsmYesNo(attribute.value);
    }
    if (attribute.value_type === 'status') {
        return {
            working: 'Работает',
            needs_repair: 'Требуется ремонт'
        }[attribute.value] || attribute.value;
    }
    return attribute.value;
}

function escapeHtml(value) {
    const element = document.createElement('div');
    element.textContent = String(value ?? '');
    return element.innerHTML;
}

/**
 * Получить цвет на основе качества покрытия
 */
function getQualityColor(quality) {
    const colors = {
        1: '#e74c3c',
        2: '#e67e22',
        3: '#f39c12',
        4: '#2ecc71',
        5: '#27ae60'
    };
    return colors[quality] || '#3498db';
}

/**
 * Обновить карту с отфильтрованными велодорожками
 */
function updateMapWithFilteredBikelanes(bikelanes) {
    if (!bikelaneSourceAdded) return;
    
    // Создаём новый GeoJSON
    const geojsonData = {
        type: 'FeatureCollection',
        features: bikelanes.map(bikelane => ({
            type: 'Feature',
            properties: {
                id: bikelane.id,
                title: bikelane.title,
                track_type: bikelane.track_type_display,
                quality: bikelane.quality,
                quality_display: bikelane.quality_display,
                color: bikelane.color || getQualityColor(bikelane.quality)
            },
            geometry: bikelane.geometry
        }))
    };
    
    // Обновляем источник
    cityMap.getSource('bikelanes').setData(geojsonData);
    
    // Подгоняем карту
    if (bikelanes.length > 0) {
        const coordinates = geojsonData.features.flatMap(f => f.geometry.coordinates);
        const bounds = coordinates.reduce((bounds, coord) => {
            return bounds.extend(coord);
        }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));
        
        cityMap.fitBounds(bounds, { padding: 50 });
    }
}

/**
 * Инициализация карты в модалке
 */
function initModalMap(bikelane) {
    if (!bikelane.geometry || !bikelane.geometry.coordinates) {
        return;
    }

    if (!configureMapbox('modalMap')) {
        return;
    }
    
    const modalMap = new mapboxgl.Map({
        container: 'modalMap',
        style: 'mapbox://styles/mapbox/light-v11',
        center: bikelane.geometry.coordinates[0], // [lng, lat]
        zoom: 13
    });
    
    modalMap.on('load', function() {
        // Добавляем линию велодорожки
        modalMap.addSource('modal-bikelane', {
            type: 'geojson',
            data: {
                type: 'Feature',
                geometry: bikelane.geometry
            }
        });
        
        modalMap.addLayer({
            id: 'modal-bikelane-layer',
            type: 'line',
            source: 'modal-bikelane',
            paint: {
                'line-color': bikelane.color || getQualityColor(bikelane.quality),
                'line-width': 4,
                'line-opacity': 0.8
            }
        });
        
        // Подгоняем карту под линию
        const coordinates = bikelane.geometry.coordinates;
        const bounds = coordinates.reduce((bounds, coord) => {
            return bounds.extend(coord);
        }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));
        
        modalMap.fitBounds(bounds, { padding: 20 });
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('Инициализация страницы города');
    initPersistentFilters();
    initBikelanesSorting();
    initCityMobileTabs();
    initCityMap();
    initCityGeolocation();
    
    // Закрытие модалки по Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            if (document.querySelector('.photo-modal-overlay')) {
                closePhotoGallery();
                return;
            }

            closeBikelaneModal();
            closeFiltersModal();
        }

        if (!document.querySelector('.photo-modal-overlay')) {
            return;
        }

        if (e.key === 'ArrowLeft') {
            changePhotoGalleryImage(-1);
        }

        if (e.key === 'ArrowRight') {
            changePhotoGalleryImage(1);
        }
    });
});

// === Функции для модалок объектов карты ===

async function showInfrastructureModal(infrastructureId) {
    const modal = document.getElementById('bikelaneModal');
    const modalContent = document.getElementById('modalContent');

    modal.style.display = 'flex';
    modalContent.innerHTML = '<div class="loading">Загрузка...</div>';

    try {
        const response = await fetch(`/api/infrastructure/${infrastructureId}`);
        if (!response.ok) {
            throw new Error('Ошибка загрузки данных');
        }

        const data = await response.json();
        const point = data.infrastructure;
        const details = Array.isArray(point.attributes)
            ? point.attributes
            : [];

        let html = `
            <div id="modalMap" class="modal-map"></div>

            <div class="island">
                <h3 class="modal-bikelane-title prime100 tac">${escapeHtml(point.title)}</h3>
                <span class="line-grid gap-m w100 jsc">
                    <span class="badge_s bgsecondary20">
                        <h6 class="black100">${escapeHtml(point.type_display)}</h6>
                    </span>
                </span>
            </div>
        `;

        if (point.description) {
            html += `
                <div class="island">
                    <p class="modal-bikelane-title prime100">${escapeHtml(point.description)}</p>
                </div>
            `;
        }

        if (details.length) {
            html += '<div class="island">';
            details.forEach((attribute) => {
                const value = formatInfrastructureAttributeValue(attribute);
                html += `<p class="prime100">${escapeHtml(attribute.label)}: ${escapeHtml(value)}</p>`;
            });
            html += '</div>';
        }

        if (point.photos && point.photos.length) {
            html += '<div class="modal-photos"><div class="modal-photos-grid">';
            point.photos.forEach((photo, index) => {
                html += `
                    <div class="modal-photo">
                        <img
                            src="/static/${encodeURI(photo)}"
                            alt="Фото объекта ${index + 1}"
                            class="modal-photo-image"
                            data-photo-index="${index}">
                    </div>
                `;
            });
            html += '</div></div>';
        }

        html += `
            <div id="objectReviews" class="object-reviews-loading">
                <div class="loading">Загрузка отзывов...</div>
            </div>

            <div class="island">
                <div class="modal-actions">
                    ${point.edit_url ? `
                        <a class="button__label btn_black" href="${escapeHtml(point.edit_url)}">
                            Редактировать
                        </a>
                    ` : ''}
                    <button class="button_square_label close" onclick="closeBikelaneModal()">
                        <img src="/static/img/icon/cross.svg" alt="Закрыть" class="icon-small arrow_down">
                    </button>
                </div>
            </div>
            <p style="margin-top:8px" class="secondary100 tac">ID: ${point.id}</p>
        `;

        modalContent.innerHTML = html;
        initModalPhotoGallery(point.photos || []);
        initObjectReviews('infrastructure', point.id);
        setTimeout(() => initInfrastructureModalMap(point), 100);
    } catch (error) {
        console.error('Ошибка загрузки объекта инфраструктуры:', error);
        modalContent.innerHTML = `
            <div class="loading">
                <p style="color: var(--secondary100);">Ошибка загрузки данных</p>
                <button class="button_square_label btn_gray" onclick="closeBikelaneModal()" style="margin-top: var(--spacer-m);">
                    Закрыть
                </button>
            </div>
        `;
    }
}

function initInfrastructureModalMap(point) {
    if (!Array.isArray(point.coordinates) || !configureMapbox('modalMap')) {
        return;
    }

    const modalMap = new mapboxgl.Map({
        container: 'modalMap',
        style: 'mapbox://styles/mapbox/light-v11',
        center: point.coordinates,
        zoom: 16
    });
    const iconName = point.type === 'bicycle_repair_station'
        ? 'repair.svg'
        : 'parking.svg';
    const markerElement = document.createElement('div');
    const markerIcon = document.createElement('img');
    markerElement.className = 'infrastructure-marker';
    markerIcon.src = `/static/img/icon/${iconName}`;
    markerIcon.alt = '';
    markerElement.appendChild(markerIcon);

    new mapboxgl.Marker({
        element: markerElement,
        anchor: 'bottom'
    })
        .setLngLat(point.coordinates)
        .addTo(modalMap);
}

async function showBikelaneModal(bikelaneId) {
    console.log('Открытие модалки для велодорожки:', bikelaneId);
    
    const modal = document.getElementById('bikelaneModal');
    const modalContent = document.getElementById('modalContent');
    
    modal.style.display = 'flex';
    modalContent.innerHTML = '<div class="loading">Загрузка...</div>';
    
    try {
        const response = await fetch(`/api/bikelane/${bikelaneId}`);
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки данных');
        }
        
        const data = await response.json();
        const bikelane = data.bikelane;
        
        let html = `

            <!--Map-->
            <div id="modalMap" class="modal-map"></div>

            <div class="island">
            <h3 class="modal-bikelane-title prime100 tac">${bikelane.title}</h3>
                ${bikelane.is_bus_lane ? '' : `
                <span class="line-grid gap-m w100 jsc">

                    <!-- Type -->
                    <span class="badge_s bgsecondary20">
                        <h6 class="black100">${bikelane.track_type_display}</h6>
                    </span>


                    <!-- Distance -->
                    <span class="badge_s bgsecondary20">
                        <img class="size_m" src="/static/img/icon/distance.svg" alt="Road Icon">
                        <h6 class="black100">${bikelane.length} км</h6>
                    </span>

                    <!-- Overall rating -->
                    <span class="badge_s bgsecondary20">
                        <h6 class="black100">★ ${bikelane.overall_quality}/5</h6>
                    </span>

                    <!-- Direction -->
                    <span class="badge_s bgsecondary20">
                        <h6 class="black100">Односторонняя — ${bikelane.is_one_way ? 'Да' : 'Нет'}</h6>
                    </span>
                </span>
                `}
            </div>

            ${bikelane.is_bus_lane ? '' : `
            <div class="island">
                <p class="modal-bikelane-title prime100">
                    ${bikelane.description}
                </p>

            </div>
            `}
        `;
        
        if (bikelane.photos && bikelane.photos.length > 0) {
            html += `
                <div class="modal-photos">
                    <div class="modal-photos-grid">
            `;
            
            bikelane.photos.forEach((photo, index) => {
                html += `
                    <div class="modal-photo">
                        <img
                            src="/static/${photo}"
                            alt="Фото объекта ${index + 1}"
                            class="modal-photo-image"
                            data-photo-index="${index}">
                    </div>
                `;
            });
            
            html += `</div></div>`;
        }
        
        if (!bikelane.is_bus_lane && bikelane.videos && bikelane.videos.length > 0) {
            html += `<div class="modal-videos"><h3 class="prime100">Видео</h3>`;
            
            bikelane.videos.forEach(videoUrl => {
                if (videoUrl.includes('youtube.com') || videoUrl.includes('youtu.be')) {
                    const videoId = extractYouTubeId(videoUrl);
                    if (videoId) {
                        html += `
                            <div class="modal-video">
                                <iframe src="https://www.youtube.com/embed/${videoId}" 
                                        allowfullscreen></iframe>
                            </div>
                        `;
                    }
                } else if (videoUrl.endsWith('.mp4')) {
                    html += `
                        <div class="modal-video">
                            <video controls style="width: 100%;">
                                <source src="${videoUrl}" type="video/mp4">
                            </video>
                        </div>
                    `;
                }
            });
            
            html += `</div>`;
        }
        
        html += `
            <div id="objectReviews" class="object-reviews-loading">
                <div class="loading">Загрузка отзывов...</div>
            </div>

            <div class="island">
                <div class="modal-author">
                    <img src="${bikelane.author.avatar || '/static/img/avatar-placeholder.jpg'}" 
                        alt="${bikelane.author.nickname}" 
                        class="author-avatar">
                    <div class="author-info">
                        <div class="author-name">${bikelane.author.nickname}</div>
                        <div class="author-date">Добавлено ${formatDate(bikelane.created_at)}</div>
                    </div>
                </div>

                <div class="modal-actions">
                    ${
                      bikelane.edit_url
                        ? `
                    <a class="button__label btn_black" href="${bikelane.edit_url}">
                        Редактировать
                    </a>
                    `
                        : ''
                    }
                    <button class="button_square_label close" onclick="closeBikelaneModal()">
                        <img src="/static/img/icon/cross.svg" alt="Закрыть" class="icon-small arrow_down">
                    </button>


                </div>
            </div>

            <p style="margin-top:8px" class="secondary100 tac">ID: ${bikelane.id}</p>
                
            
        `;
        
        modalContent.innerHTML = html;
        initModalPhotoGallery(bikelane.photos || []);
        initObjectReviews('bikelane', bikelane.id);
        
        setTimeout(() => {
            initModalMap(bikelane);
        }, 100);
        
    } catch (error) {
        console.error('Ошибка загрузки велодорожки:', error);
        modalContent.innerHTML = `
            <div class="loading">
                <p style="color: var(--secondary100);">Ошибка загрузки данных</p>
                <button class="button_square_label btn_gray" onclick="closeBikelaneModal()" style="margin-top: var(--spacer-m);">
                    Закрыть
                </button>
            </div>
        `;
    }
}

function reviewCountLabel(count) {
    const value = Math.abs(Number(count) || 0);
    const lastTwo = value % 100;
    const last = value % 10;
    if (lastTwo >= 11 && lastTwo <= 14) {
        return `${value} отзывов`;
    }
    if (last === 1) {
        return `${value} отзыв`;
    }
    if (last >= 2 && last <= 4) {
        return `${value} отзыва`;
    }
    return `${value} отзывов`;
}

function renderReviewStars(rating, interactive = false) {
    const normalizedRating = Number(rating) || 0;
    return [1, 2, 3, 4, 5].map((value) => {
        const activeClass = value <= normalizedRating ? ' is-active' : '';
        if (interactive) {
            return `
                <button
                    type="button"
                    class="review-star-button${activeClass}"
                    data-rating="${value}"
                    aria-label="${value} из 5"
                    aria-pressed="${value <= normalizedRating ? 'true' : 'false'}">★</button>
            `;
        }
        return `<span class="review-star${activeClass}" aria-hidden="true">★</span>`;
    }).join('');
}

function renderReviewCard(review) {
    const avatar = review.author.avatar || '/static/img/avatar-placeholder.jpg';
    const photos = Array.isArray(review.photos) ? review.photos : [];
    const photosHtml = photos.length
        ? `
            <div class="review-photos">
                ${photos.map((photo, index) => `
                    <button
                        type="button"
                        class="review-photo-button"
                        data-review-photo-group="${review.id}"
                        data-photo-index="${index}"
                        aria-label="Открыть фото ${index + 1}">
                        <img
                            src="/static/${escapeHtml(encodeURI(photo))}"
                            alt="Фото к отзыву ${index + 1}"
                            class="review-photo-image">
                    </button>
                `).join('')}
            </div>
        `
        : '';

    return `
        <article class="review-card">
            <div class="review-author-row">
                <img
                    src="${escapeHtml(avatar)}"
                    alt="${escapeHtml(review.author.nickname)}"
                    class="review-author-avatar">
                <div class="review-author-copy">
                    <strong>${escapeHtml(review.author.nickname)}</strong>
                    <span>${formatDate(review.updated_at || review.created_at)}</span>
                </div>
            </div>
            <div class="review-card-rating" aria-label="Оценка ${review.rating} из 5">
                ${renderReviewStars(review.rating)}
            </div>
            ${review.text ? `<p class="review-text">${escapeHtml(review.text)}</p>` : ''}
            ${photosHtml}
        </article>
    `;
}

function renderObjectReviews(data, targetType, targetId) {
    const container = document.getElementById('objectReviews');
    const ownReview = data.current_user_review || null;
    const currentRating = ownReview ? ownReview.rating : 0;
    const average = data.summary.average;
    const reviews = Array.isArray(data.reviews) ? data.reviews : [];
    const formHtml = data.authenticated
        ? `
            <form class="review-form" id="objectReviewForm">
                <h3 class="prime100">${ownReview ? 'Ваш отзыв' : 'Оцените это место'}</h3>
                <div class="review-rating-input" role="radiogroup" aria-label="Оценка">
                    ${renderReviewStars(currentRating, true)}
                </div>
                <input type="hidden" name="rating" value="${currentRating}">
                <textarea
                    name="text"
                    maxlength="${data.max_text_length}"
                    placeholder="Напишите отзыв">${escapeHtml(ownReview ? ownReview.text : '')}</textarea>
                <label class="review-photo-input">
                    <span>Прикрепить фото (до ${data.max_photos})</span>
                    <input type="file" name="photos" multiple accept="image/*">
                </label>
                <button
                    type="submit"
                    class="button__label btn_black review-submit"
                    ${currentRating ? '' : 'disabled'}>
                    ${ownReview ? 'Обновить отзыв' : 'Опубликовать отзыв'}
                </button>
                <p class="review-form-status" aria-live="polite"></p>
            </form>
        `
        : `
            <div class="review-login-prompt">
                <p>Войдите, чтобы поставить оценку и написать отзыв.</p>
                <a class="button__label btn_black" href="${escapeHtml(data.login_url)}">Войти</a>
            </div>
        `;

    if (!container) {
        return;
    }

    container.className = 'object-reviews';
    container.innerHTML = `
        <section class="review-summary island">
            <div class="review-average">${average === null ? '—' : average.toFixed(1)}</div>
            <div class="review-summary-copy">
                <div class="review-summary-stars">
                    ${renderReviewStars(Math.round(average || 0))}
                </div>
                <span>${reviewCountLabel(data.summary.count)}</span>
            </div>
        </section>

        <section class="review-editor island">
            ${formHtml}
        </section>

        <section class="review-list-section">
            <div class="review-list-heading">
                <h3>${reviewCountLabel(data.summary.count)}</h3>
            </div>
            <div class="review-list">
                ${
                    reviews.length
                        ? reviews.map(renderReviewCard).join('')
                        : '<div class="island review-empty">Отзывов пока нет — будьте первым.</div>'
                }
            </div>
        </section>
    `;

    const form = document.getElementById('objectReviewForm');
    if (form) {
        const ratingInput = form.querySelector('input[name="rating"]');
        const submitButton = form.querySelector('.review-submit');
        form.querySelectorAll('.review-star-button').forEach((button) => {
            button.addEventListener('click', function() {
                const rating = Number(this.dataset.rating);
                ratingInput.value = String(rating);
                submitButton.disabled = false;
                form.querySelectorAll('.review-star-button').forEach((star) => {
                    const isActive = Number(star.dataset.rating) <= rating;
                    star.classList.toggle('is-active', isActive);
                    star.setAttribute('aria-pressed', isActive ? 'true' : 'false');
                });
            });
        });

        form.addEventListener('submit', async function(event) {
            event.preventDefault();
            const status = form.querySelector('.review-form-status');
            submitButton.disabled = true;
            status.textContent = 'Сохраняем отзыв...';

            try {
                const response = await fetch(
                    `/api/reviews/${targetType}/${targetId}`,
                    {
                        method: 'POST',
                        body: new FormData(form)
                    }
                );
                const result = await response.json();
                if (!response.ok || !result.success) {
                    throw new Error(result.error || 'Не удалось сохранить отзыв.');
                }
                await initObjectReviews(targetType, targetId);
            } catch (error) {
                status.textContent = error.message;
                submitButton.disabled = false;
            }
        });
    }

    const photoGroups = new Map(
        reviews.map((review) => [
            String(review.id),
            (review.photos || []).map((photo) => `/static/${photo}`)
        ])
    );
    container.querySelectorAll('.review-photo-button').forEach((button) => {
        button.addEventListener('click', function() {
            const photos = photoGroups.get(this.dataset.reviewPhotoGroup) || [];
            if (!photos.length) {
                return;
            }
            photoGalleryState.photos = photos;
            openPhotoGallery(Number(this.dataset.photoIndex) || 0);
        });
    });
}

async function initObjectReviews(targetType, targetId) {
    const container = document.getElementById('objectReviews');
    if (!container) {
        return;
    }

    const requestKey = `${targetType}:${targetId}`;
    container.dataset.reviewRequest = requestKey;

    try {
        const response = await fetch(`/api/reviews/${targetType}/${targetId}`);
        if (!response.ok) {
            throw new Error('Не удалось загрузить отзывы.');
        }
        const data = await response.json();
        const currentContainer = document.getElementById('objectReviews');
        if (
            !currentContainer
            || currentContainer.dataset.reviewRequest !== requestKey
        ) {
            return;
        }
        renderObjectReviews(data, targetType, targetId);
    } catch (error) {
        const currentContainer = document.getElementById('objectReviews');
        if (currentContainer) {
            currentContainer.innerHTML = `
                <div class="island review-empty">${escapeHtml(error.message)}</div>
            `;
        }
    }
}

function closeBikelaneModal() {
    const modal = document.getElementById('bikelaneModal');
    if (!modal) {
        return;
    }

    modal.style.display = 'none';
}

function initModalPhotoGallery(photos) {
    const photoElements = document.querySelectorAll('.modal-photo-image');

    if (!photoElements.length) {
        return;
    }

    photoGalleryState.photos = photos.map((photo) => `/static/${photo}`);
    photoGalleryState.currentIndex = 0;

    photoElements.forEach((photoElement) => {
        photoElement.addEventListener('click', function() {
            const index = Number.parseInt(this.dataset.photoIndex || '0', 10);
            openPhotoGallery(index);
        });
    });
}

function openPhotoGallery(index) {
    if (!photoGalleryState.photos.length) {
        return;
    }

    photoGalleryState.currentIndex = index;

    const existingOverlay = document.querySelector('.photo-modal-overlay');
    if (existingOverlay) {
        existingOverlay.remove();
    }

    const overlay = document.createElement('div');
    overlay.className = 'photo-modal-overlay';
    overlay.innerHTML = `
        <div class="photo-modal" onclick="event.stopPropagation()">

            
            <button class="button_square_label close" type="button" aria-label="Закрыть галерею" onclick="closePhotoGallery()">
                <img src="/static/img/icon/cross.svg" alt="Закрыть">
            </button>

            <img src="" alt="Фото велодорожки" id="photoGalleryImage">

            <div class="photo-container">
                <button class="button_square_label btn_gray " type="button" aria-label="Предыдущее фото" onclick="changePhotoGalleryImage(-1)">
                    <img src="/static/img/icon/chevron_left.svg" alt="Предыдущее фото">
                </button>

                <div class="photo-info" id="photoGalleryCounter"></div>
            
                <button class="button_square_label btn_gray " type="button" aria-label="Следующее фото" onclick="changePhotoGalleryImage(1)">
                    <img src="/static/img/icon/chevron_right.svg" alt="Следующее фото">
                </button>
            
            </div>
    `;

    overlay.addEventListener('click', closePhotoGallery);
    document.body.appendChild(overlay);
    document.body.classList.add('photo-gallery-open');

    updatePhotoGalleryView();
}

function updatePhotoGalleryView() {
    const image = document.getElementById('photoGalleryImage');
    const counter = document.getElementById('photoGalleryCounter');
    const prevButton = document.querySelector('.photo-modal-prev');
    const nextButton = document.querySelector('.photo-modal-next');

    if (!image || !counter || !photoGalleryState.photos.length) {
        return;
    }

    image.src = photoGalleryState.photos[photoGalleryState.currentIndex];
    counter.textContent = `${photoGalleryState.currentIndex + 1} / ${photoGalleryState.photos.length}`;

    const hasMultiplePhotos = photoGalleryState.photos.length > 1;
    if (prevButton) {
        prevButton.style.display = hasMultiplePhotos ? 'flex' : 'none';
    }
    if (nextButton) {
        nextButton.style.display = hasMultiplePhotos ? 'flex' : 'none';
    }
}

function changePhotoGalleryImage(step) {
    if (!photoGalleryState.photos.length) {
        return;
    }

    const total = photoGalleryState.photos.length;
    photoGalleryState.currentIndex = (photoGalleryState.currentIndex + step + total) % total;
    updatePhotoGalleryView();
}

function closePhotoGallery() {
    const overlay = document.querySelector('.photo-modal-overlay');
    if (overlay) {
        overlay.remove();
    }

    document.body.classList.remove('photo-gallery-open');
}

function extractYouTubeId(url) {
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)/,
        /youtube\.com\/embed\/([a-zA-Z0-9_-]+)/
    ];
    
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) {
            return match[1];
        }
    }
    
    return null;
}

function formatDate(dateString) {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
        return 'сегодня';
    } else if (diffDays === 1) {
        return 'вчера';
    } else if (diffDays < 7) {
        return `${diffDays} дней назад`;
    } else {
        return date.toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });
    }
}

// === Функции для фильтров ===

function openFiltersModal() {
    const modal = document.getElementById('filtersModal');
    if (!modal) {
        return;
    }

    modal.style.display = 'flex';
}

function closeFiltersModal() {
    const modal = document.getElementById('filtersModal');
    if (!modal) {
        return;
    }

    modal.style.display = 'none';
}

function getFilterState() {
    return {
        trackType: document.getElementById('trackTypeFilter')?.value || '',
        quality: document.getElementById('qualityFilter')?.value || '',
        showBikelanes: document.getElementById('showBikelanesFilter')?.checked ?? true,
        showBusLanes: document.getElementById('showBusLanesFilter')?.checked ?? true,
        showParking: document.getElementById('showParkingFilter')?.checked ?? true,
        showRepair: document.getElementById('showRepairFilter')?.checked ?? true
    };
}

function saveFilterState() {
    try {
        localStorage.setItem(
            CITY_MAP_FILTERS_STORAGE_KEY,
            JSON.stringify(getFilterState())
        );
    } catch (error) {
        console.warn('Не удалось сохранить фильтры карты:', error);
    }
}

function restoreFilterState() {
    let savedState;
    try {
        savedState = JSON.parse(
            localStorage.getItem(CITY_MAP_FILTERS_STORAGE_KEY) || 'null'
        );
    } catch (error) {
        console.warn('Не удалось восстановить фильтры карты:', error);
        return;
    }

    if (!savedState || typeof savedState !== 'object') {
        return;
    }

    const trackTypeFilter = document.getElementById('trackTypeFilter');
    const qualityFilter = document.getElementById('qualityFilter');
    if (
        trackTypeFilter
        && Array.from(trackTypeFilter.options).some(
            (option) => option.value === savedState.trackType
        )
    ) {
        trackTypeFilter.value = savedState.trackType;
    }
    if (
        qualityFilter
        && Array.from(qualityFilter.options).some(
            (option) => option.value === savedState.quality
        )
    ) {
        qualityFilter.value = savedState.quality;
    }

    [
        ['showBikelanesFilter', 'showBikelanes'],
        ['showBusLanesFilter', 'showBusLanes'],
        ['showParkingFilter', 'showParking'],
        ['showRepairFilter', 'showRepair']
    ].forEach(([elementId, property]) => {
        const input = document.getElementById(elementId);
        if (input && typeof savedState[property] === 'boolean') {
            input.checked = savedState[property];
        }
    });
}

function initPersistentFilters() {
    restoreFilterState();
    [
        'trackTypeFilter',
        'qualityFilter',
        'showBikelanesFilter',
        'showBusLanesFilter',
        'showParkingFilter',
        'showRepairFilter'
    ].forEach((elementId) => {
        document.getElementById(elementId)?.addEventListener(
            'change',
            saveFilterState
        );
    });
    updateFilterBadge();
}

function applyCurrentFilters() {
    const trackType = document.getElementById('trackTypeFilter')?.value || '';
    const quality = document.getElementById('qualityFilter')?.value || '';
    filterBikelanes(trackType, quality);
    applyMapLayerFilters();
    updateFilterBadge();
}

function applyFilters() {
    saveFilterState();
    applyCurrentFilters();
    closeFiltersModal();
}

function resetFilters() {
    document.getElementById('trackTypeFilter').value = '';
    document.getElementById('qualityFilter').value = '';
    document.getElementById('searchInput').value = '';
    document.getElementById('showBikelanesFilter').checked = true;
    document.getElementById('showBusLanesFilter').checked = true;
    document.getElementById('showParkingFilter').checked = true;
    document.getElementById('showRepairFilter').checked = true;
    
    saveFilterState();
    applyCurrentFilters();
    closeFiltersModal();
}

function filterBikelanes(trackType, quality) {
    const searchQuery = document.getElementById('searchInput').value.toLowerCase().trim();
    const showBikelanes = document.getElementById('showBikelanesFilter')?.checked ?? true;
    const showBusLanes = document.getElementById('showBusLanesFilter')?.checked ?? true;
    
    let filteredBikelanes = window.bikelanesData.filter(bl => {
        if (searchQuery && !bl.title.toLowerCase().includes(searchQuery)) {
            return false;
        }

        const isBusLane = bl.track_type === 'bus_lane' || bl.is_bus_lane;
        if (isBusLane) {
            return showBusLanes;
        }
        if (!showBikelanes) {
            return false;
        }
        if (trackType && bl.track_type !== trackType) {
            return false;
        }
        if (quality && bl.quality !== parseInt(quality)) {
            return false;
        }

        return true;
    });

    filteredBikelanes = sortBikelanes(filteredBikelanes);
    updateMapWithFilteredBikelanes(filteredBikelanes);
    updateBikelanesList(filteredBikelanes);
}

function normalizeBikelaneTitle(title) {
    return String(title || '')
        .toLocaleLowerCase('ru-RU')
        .replace(/(^|\s)(?:улица|ул\.?)(?=\s|$)/giu, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function compareBikelaneTitles(first, second) {
    return normalizeBikelaneTitle(first.title).localeCompare(
        normalizeBikelaneTitle(second.title),
        'ru',
        { sensitivity: 'base', numeric: true }
    );
}

function sortBikelanes(bikelanes) {
    const sortMode = document.getElementById('bikelanesSort')?.value || 'date_desc';
    const sortedBikelanes = [...bikelanes];

    sortedBikelanes.sort((first, second) => {
        if (sortMode === 'alphabetical') {
            return compareBikelaneTitles(first, second);
        }
        if (sortMode === 'distance_desc') {
            return (Number(second.length) || 0) - (Number(first.length) || 0)
                || compareBikelaneTitles(first, second);
        }
        if (sortMode === 'quality_desc') {
            return (Number(second.overall_quality) || 0) - (Number(first.overall_quality) || 0)
                || compareBikelaneTitles(first, second);
        }

        const firstCreatedAt = Date.parse(first.created_at || '') || 0;
        const secondCreatedAt = Date.parse(second.created_at || '') || 0;
        return secondCreatedAt - firstCreatedAt
            || (Number(second.id) || 0) - (Number(first.id) || 0);
    });

    return sortedBikelanes;
}

function initBikelanesSorting() {
    document.getElementById('bikelanesSort')?.addEventListener(
        'change',
        applyCurrentFilters
    );
}

function applyMapLayerFilters() {
    const showBikelanes = document.getElementById('showBikelanesFilter')?.checked ?? true;
    const showBusLanes = document.getElementById('showBusLanesFilter')?.checked ?? true;
    const showParking = document.getElementById('showParkingFilter')?.checked ?? true;
    const showRepair = document.getElementById('showRepairFilter')?.checked ?? true;

    if (cityMap && cityMap.getLayer('bikelanes-layer')) {
        cityMap.setLayoutProperty(
            'bikelanes-layer',
            'visibility',
            showBikelanes || showBusLanes ? 'visible' : 'none'
        );
    }

    infrastructureMarkers.forEach((item) => {
        const isVisible = item.type === 'bicycle_repair_station'
            ? showRepair
            : showParking;
        item.element.style.display = isVisible ? '' : 'none';
    });
}

function updateBikelanesList(bikelanes) {
    const listContainer = document.querySelector('.bikelanes-list');
    
    if (!listContainer) return;
    
    if (bikelanes.length === 0) {
        listContainer.innerHTML = '<p class="secondary100" style="padding: var(--spacer-m); text-align: center;">Велодорожки не найдены</p>';
        return;
    }
    
    listContainer.innerHTML = '';
    
    bikelanes.forEach(bikelane => {
        const item = document.createElement('div');
        item.className = 'bikelane-item';
        item.setAttribute('data-bikelane-id', bikelane.id);
        item.onclick = () => showBikelaneModal(bikelane.id);
        
        item.innerHTML = `
            <div class="hstack gap-m aic">
                <div class="quality-indicator" style="background-color: ${bikelane.color || getQualityColor(bikelane.overall_quality ?? bikelane.quality)};"></div>
                
                <div class="vstack gap-s w100">
                    <h4 class="prime100 bikelane-title">${bikelane.title}</h4>
                    <p class="secondary100 bikelane-meta">
                        ${bikelane.is_bus_lane
                            ? bikelane.track_type_display
                            : `${bikelane.track_type_display} • ★ ${bikelane.overall_quality}/5 • ${bikelane.length} км`}
                    </p>
                </div>
                
                <img src="/static/img/icon/chevron_right.svg" 
                     alt="Открыть" 
                     class="icon-small chevron_right">
            </div>
        `;
        
        listContainer.appendChild(item);
    });
}

function updateFilterBadge() {
    const trackType = document.getElementById('trackTypeFilter').value;
    const quality = document.getElementById('qualityFilter').value;
    const badge = document.getElementById('filterBadge');
    const showBikelanes = document.getElementById('showBikelanesFilter')?.checked ?? true;
    const showBusLanes = document.getElementById('showBusLanesFilter')?.checked ?? true;
    const showParking = document.getElementById('showParkingFilter')?.checked ?? true;
    const showRepair = document.getElementById('showRepairFilter')?.checked ?? true;
    
    let count = 0;
    if (trackType) count++;
    if (quality) count++;
    if (!showBikelanes) count++;
    if (!showBusLanes) count++;
    if (!showParking) count++;
    if (!showRepair) count++;
    
    if (count > 0) {
        badge.textContent = count;
        badge.style.display = 'flex';
    } else {
        badge.style.display = 'none';
    }
}

// Живой поиск
const searchInput = document.getElementById('searchInput');
if (searchInput) {
    searchInput.addEventListener('input', function() {
        const trackType = document.getElementById('trackTypeFilter').value;
        const quality = document.getElementById('qualityFilter').value;
        filterBikelanes(trackType, quality);
    });
}
