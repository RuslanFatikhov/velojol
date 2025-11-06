/**
 * Скрипт для карты города с Mapbox GL JS
 */

// Токен Mapbox
mapboxgl.accessToken = 'pk.eyJ1IjoiZnV6bGFuIiwiYSI6ImNsc2N3dnhuNTBrZXYya28xeG1mb3k3N3AifQ.bLjMuXA5JfgBW0pwtjQxxA';

let cityMap;
let bikelaneSourceAdded = false;

/**
 * Инициализация карты города
 */
function initCityMap() {
    console.log('Инициализация Mapbox карты...');
    
    if (!window.cityData) {
        console.error('Данные города не найдены');
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
                color: getQualityColor(bikelane.quality)
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
                color: getQualityColor(bikelane.quality)
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
                'line-color': getQualityColor(bikelane.quality),
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
    initCityMap();
    
    // Закрытие модалки по Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeBikelaneModal();
            closeFiltersModal();
        }
    });
});

// === Функции для модалки велодорожки (из старого файла) ===

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
                </span>
            </div>

            <div class="island">
                <p class="modal-bikelane-description prime100">
                    ${bikelane.description}
                </p>

            </div>
        `;
        
        if (bikelane.photos && bikelane.photos.length > 0) {
            html += `
                <div class="modal-photos">
                    <h3 class="prime100">Фотографии</h3>
                    <div class="modal-photos-grid">
            `;
            
            bikelane.photos.forEach(photo => {
                html += `
                    <div class="modal-photo">
                        <img src="/static/${photo}" alt="Фото велодорожки">
                    </div>
                `;
            });
            
            html += `</div></div>`;
        }
        
        if (bikelane.videos && bikelane.videos.length > 0) {
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
                    <button class="button_square_label btn_gray" onclick="closeBikelaneModal()">
                        Закрыть
                    </button>
                </div>
            </div>
                
                
            
        `;
        
        modalContent.innerHTML = html;
        
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

function closeBikelaneModal() {
    const modal = document.getElementById('bikelaneModal');
    modal.style.display = 'none';
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
    modal.style.display = 'flex';
}

function closeFiltersModal() {
    const modal = document.getElementById('filtersModal');
    modal.style.display = 'none';
}

function applyFilters() {
    const trackType = document.getElementById('trackTypeFilter').value;
    const quality = document.getElementById('qualityFilter').value;
    
    filterBikelanes(trackType, quality);
    updateFilterBadge();
    closeFiltersModal();
}

function resetFilters() {
    document.getElementById('trackTypeFilter').value = '';
    document.getElementById('qualityFilter').value = '';
    document.getElementById('searchInput').value = '';
    
    filterBikelanes('', '');
    updateFilterBadge();
    closeFiltersModal();
}

function filterBikelanes(trackType, quality) {
    const searchQuery = document.getElementById('searchInput').value.toLowerCase().trim();
    
    let filteredBikelanes = window.bikelanesData.filter(bl => {
        let match = true;
        
        if (searchQuery && !bl.title.toLowerCase().includes(searchQuery)) {
            match = false;
        }
        
        if (trackType && bl.track_type !== trackType) {
            match = false;
        }
        
        if (quality && bl.quality !== parseInt(quality)) {
            match = false;
        }
        
        return match;
    });
    
    updateMapWithFilteredBikelanes(filteredBikelanes);
    updateBikelanesList(filteredBikelanes);
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
                <div class="quality-indicator" style="background-color: ${getQualityColor(bikelane.quality)};"></div>
                
                <div class="vstack gap-s w100">
                    <h4 class="prime100 bikelane-title">${bikelane.title}</h4>
                    <p class="secondary100 bikelane-meta">
                        ${bikelane.track_type_display} • ${bikelane.quality_display} • ${bikelane.length} км
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
    
    let count = 0;
    if (trackType) count++;
    if (quality) count++;
    
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
