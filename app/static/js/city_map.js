/**
 * Скрипт для страницы города с картой велодорожек и модалкой (Скорее всего удалить!)
 */


let cityMap;
let bikelaneLines = [];

/**
 * Инициализация карты города
 */
function initCityMap() {
    console.log('Инициализация карты города...');
    
    if (!window.cityData) {
        console.error('Данные города не найдены');
        return;
    }
    
    // Создаём карту
    cityMap = L.map('cityMap').setView(window.cityData.coords, window.cityData.zoom);
    
    // Добавляем тайлы OpenStreetMap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(cityMap);
    
    console.log('Карта создана');
    
    // Рисуем велодорожки на карте
    drawBikelanes();
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
    
    // Очищаем предыдущие линии
    bikelaneLines.forEach(line => cityMap.removeLayer(line));
    bikelaneLines = [];
    
    // Для подгонки карты под все велодорожки
    let allCoords = [];
    
    window.bikelanesData.forEach(bikelane => {
        if (!bikelane.geometry || !bikelane.geometry.coordinates) {
            console.warn(`У велодорожки ${bikelane.id} нет геометрии`);
            return;
        }
        
        // Конвертируем координаты из GeoJSON [lng, lat] в Leaflet [lat, lng]
        const latlngs = bikelane.geometry.coordinates.map(coord => [coord[1], coord[0]]);
        allCoords = allCoords.concat(latlngs);
        
        // Определяем цвет на основе качества (от 1 до 5)
        const color = getQualityColor(bikelane.quality);
        
        // Создаём линию
        const polyline = L.polyline(latlngs, {
            color: color,
            weight: 4,
            opacity: 0.8
        }).addTo(cityMap);
        
        // Добавляем попап с кратким описанием
        polyline.bindPopup(`
            <div style="min-width: 200px;">
                <strong style="font-size: 16px;">${bikelane.title}</strong><br>
                <span style="color: #666; font-size: 14px;">
                    ${bikelane.track_type_display} • ${bikelane.quality_display}
                </span><br>
                <button onclick="showBikelaneModal(${bikelane.id})" 
                        style="margin-top: 8px; padding: 6px 12px; background: var(--accent100); color: white; border: none; border-radius: 4px; cursor: pointer;">
                    Подробнее
                </button>
            </div>
        `);
        
        // Добавляем обработчик клика
        polyline.on('click', function() {
            showBikelaneModal(bikelane.id);
        });
        
        bikelaneLines.push(polyline);
    });
    
    // Подгоняем карту под все велодорожки
    if (allCoords.length > 0) {
        const bounds = L.latLngBounds(allCoords);
        cityMap.fitBounds(bounds, { padding: [50, 50] });
    }
    
    console.log('Велодорожки отрисованы');
}

/**
 * Получить цвет на основе качества покрытия
 */
function getQualityColor(quality) {
    const colors = {
        1: '#e74c3c',  // Красный - Ужасно
        2: '#e67e22',  // Оранжевый - Плохо
        3: '#f39c12',  // Жёлтый - Средне
        4: '#2ecc71',  // Зелёный - Хорошо
        5: '#27ae60'   // Тёмно-зелёный - Отлично
    };
    return colors[quality] || '#3498db';
}

/**
 * Показать модальное окно велодорожки
 */
async function showBikelaneModal(bikelaneId) {
    console.log('Открытие модалки для велодорожки:', bikelaneId);
    
    const modal = document.getElementById('bikelaneModal');
    const modalContent = document.getElementById('modalContent');
    
    // Показываем модалку с индикатором загрузки
    modal.style.display = 'flex';
    modalContent.innerHTML = '<div class="loading">Загрузка...</div>';
    
    try {
        // Загружаем данные велодорожки через API
        const response = await fetch(`/api/bikelane/${bikelaneId}`);
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки данных');
        }
        
        const data = await response.json();
        const bikelane = data.bikelane;
        
        // Формируем HTML содержимое модалки
        let html = `
            <h2 class="modal-bikelane-title prime200">${bikelane.title}</h2>
            
            <div class="modal-bikelane-meta">
                <span class="meta-badge">
                    <span>🚴</span>
                    ${bikelane.track_type_display}
                </span>
                <span class="meta-badge">
                    <span>⭐</span>
                    ${bikelane.quality_display}
                </span>
                <span class="meta-badge">
                    <span>📏</span>
                    ${bikelane.length} км
                </span>
            </div>
            
            <div class="modal-bikelane-description prime100">
                ${bikelane.description}
            </div>
        `;
        
        // Добавляем карту
        html += `
            <div id="modalMap" class="modal-map"></div>
        `;
        
        // Добавляем фотографии
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
            
            html += `
                    </div>
                </div>
            `;
        }
        
        // Добавляем видео
        if (bikelane.videos && bikelane.videos.length > 0) {
            html += `<div class="modal-videos"><h3 class="prime100">Видео</h3>`;
            
            bikelane.videos.forEach(videoUrl => {
                // Проверяем, это YouTube или обычное видео
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
        
        // Добавляем автора
        html += `
            <div class="modal-author">
                <img src="${bikelane.author.avatar || '/static/img/avatar-placeholder.jpg'}" 
                     alt="${bikelane.author.nickname}" 
                     class="author-avatar">
                <div class="author-info">
                    <div class="author-name">${bikelane.author.nickname}</div>
                    <div class="author-date">Добавлено ${formatDate(bikelane.created_at)}</div>
                </div>
            </div>
        `;
        
        // Добавляем действия
        html += `
            <div class="modal-actions">
                <button class="button_square_label btn_gray" onclick="closeBikelaneModal()">
                    Закрыть
                </button>
            </div>
        `;
        
        // Вставляем содержимое
        modalContent.innerHTML = html;
        
        // Инициализируем карту в модалке
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

/**
 * Инициализация карты в модалке
 */
function initModalMap(bikelane) {
    if (!bikelane.geometry || !bikelane.geometry.coordinates) {
        return;
    }
    
    const modalMap = L.map('modalMap').setView([43.2565, 76.9286], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(modalMap);
    
    // Рисуем линию велодорожки
    const latlngs = bikelane.geometry.coordinates.map(coord => [coord[1], coord[0]]);
    const color = getQualityColor(bikelane.quality);
    
    const polyline = L.polyline(latlngs, {
        color: color,
        weight: 4,
        opacity: 0.8
    }).addTo(modalMap);
    
    // Подгоняем карту под линию
    modalMap.fitBounds(polyline.getBounds(), { padding: [20, 20] });
}

/**
 * Закрыть модальное окно
 */
function closeBikelaneModal() {
    const modal = document.getElementById('bikelaneModal');
    modal.style.display = 'none';
}

/**
 * Извлечь ID видео из YouTube URL
 */
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

/**
 * Форматировать дату
 */
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

/**
 * Инициализация страницы
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('Инициализация страницы города');
    initCityMap();
    
    // Закрытие модалки по Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeBikelaneModal();
        }
    });
});
/**
 * Открыть модальное окно фильтров
 */
function openFiltersModal() {
    const modal = document.getElementById('filtersModal');
    modal.style.display = 'flex';
}

/**
 * Закрыть модальное окно фильтров
 */
function closeFiltersModal() {
    const modal = document.getElementById('filtersModal');
    modal.style.display = 'none';
}

/**
 * Применить фильтры
 */
function applyFilters() {
    const trackType = document.getElementById('trackTypeFilter').value;
    const quality = document.getElementById('qualityFilter').value;
    
    // Фильтруем велодорожки на карте и в списке
    filterBikelanes(trackType, quality);
    
    // Обновляем badge
    updateFilterBadge();
    
    // Закрываем модалку
    closeFiltersModal();
}

/**
 * Сбросить фильтры
 */
function resetFilters() {
    document.getElementById('trackTypeFilter').value = '';
    document.getElementById('qualityFilter').value = '';
    document.getElementById('searchInput').value = '';
    
    // Показываем все велодорожки
    filterBikelanes('', '');
    
    // Обновляем badge
    updateFilterBadge();
    
    closeFiltersModal();
}

/**
 * Фильтрация велодорожек
 */
function filterBikelanes(trackType, quality) {
    const searchQuery = document.getElementById('searchInput').value.toLowerCase().trim();
    
    // Фильтруем данные
    let filteredBikelanes = window.bikelanesData.filter(bl => {
        let match = true;
        
        // Фильтр по поиску
        if (searchQuery && !bl.title.toLowerCase().includes(searchQuery)) {
            match = false;
        }
        
        // Фильтр по типу
        if (trackType && bl.track_type !== trackType) {
            match = false;
        }
        
        // Фильтр по качеству
        if (quality && bl.quality !== parseInt(quality)) {
            match = false;
        }
        
        return match;
    });
    
    // Обновляем карту
    updateMapWithFilteredBikelanes(filteredBikelanes);
    
    // Обновляем список
    updateBikelanesList(filteredBikelanes);
}

/**
 * Обновить карту с отфильтрованными велодорожками
 */
function updateMapWithFilteredBikelanes(bikelanes) {
    // Очищаем старые линии
    bikelaneLines.forEach(line => cityMap.removeLayer(line));
    bikelaneLines = [];
    
    if (bikelanes.length === 0) return;
    
    let allCoords = [];
    
    bikelanes.forEach(bikelane => {
        if (!bikelane.geometry || !bikelane.geometry.coordinates) return;
        
        const latlngs = bikelane.geometry.coordinates.map(coord => [coord[1], coord[0]]);
        allCoords = allCoords.concat(latlngs);
        
        const color = getQualityColor(bikelane.quality);
        
        const polyline = L.polyline(latlngs, {
            color: color,
            weight: 4,
            opacity: 0.8
        }).addTo(cityMap);
        
        polyline.bindPopup(`
            <div style="min-width: 200px;">
                <strong style="font-size: 16px;">${bikelane.title}</strong><br>
                <span style="color: #666; font-size: 14px;">
                    ${bikelane.track_type_display} • ${bikelane.quality_display}
                </span><br>
                <button onclick="showBikelaneModal(${bikelane.id})" 
                        style="margin-top: 8px; padding: 6px 12px; background: var(--accent100); color: white; border: none; border-radius: 4px; cursor: pointer;">
                    Подробнее
                </button>
            </div>
        `);
        
        polyline.on('click', function() {
            showBikelaneModal(bikelane.id);
        });
        
        bikelaneLines.push(polyline);
    });
    
    if (allCoords.length > 0) {
        const bounds = L.latLngBounds(allCoords);
        cityMap.fitBounds(bounds, { padding: [50, 50] });
    }
}

/**
 * Обновить список велодорожек
 */
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

/**
 * Обновить badge с количеством активных фильтров
 */
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
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const trackType = document.getElementById('trackTypeFilter').value;
            const quality = document.getElementById('qualityFilter').value;
            filterBikelanes(trackType, quality);
        });
    }
});
