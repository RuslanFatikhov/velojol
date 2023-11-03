// Инициализация карты с использованием Mapbox
mapboxgl.accessToken = 'pk.eyJ1IjoiZnV6bGFuIiwiYSI6ImNsbjl4bXh5dDBhNHIycXA1dWM3a29wN2sifQ.DdCGdPSwOj5eASUjdiqXsg'; 

const map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/dark-v10',
    center: [57.205225, 50.278905],
    zoom: 11
});

map.on('load', () => {
    // Загрузка данных из JSON-файла
    fetch('bikePathsData-aktobe-rus.json')
        .then(response => response.json())
        .then(data => {
            data.forEach(bikePath => {
                const safetyLevels = {
                    5: { color: '#64C750', text: 'Отлично' },
                    4: { color: '#FFBD3F', text: 'Хорошо' },
                    3: { color: '#E55D47', text: 'Плохо' },
                    2: { color: '#772613', text: 'Ужасно' },
                    1: { color: '#121212', text: 'Очень небезопасно' }
                };

                const roadColor = safetyLevels[bikePath.safetyLevel]?.color || '#121212';
                const safetyText = safetyLevels[bikePath.safetyLevel]?.text || 'Неизвестно';

                map.addLayer({
                    'id': `bike-path-${bikePath.id}`,
                    'type': 'line',
                    'source': {
                        'type': 'geojson',
                        'data': {
                            'type': 'Feature',
                            'properties': {
                                'id': bikePath.id,
                                'name': bikePath.name,
                                'safetyLevel': bikePath.safetyLevel,
                                'safetyText': safetyText,
                                'description': bikePath.description,
                                'source':bikePath.source,
                                'date':bikePath.date
                            },
                            'geometry': {
                                'type': 'LineString',
                                'coordinates': bikePath.coordinates
                            }
                        }
                    },
                    'layout': {
                        'line-join': 'round',
                        'line-cap': 'round'
                    },
                    'paint': {
                        'line-color': roadColor,
                        'line-width': 4
                    }
                });

                map.on('click', `bike-path-${bikePath.id}`, handlePopup);
                map.on('touchstart', `bike-path-${bikePath.id}`, handlePopup);

                function handlePopup(e) {
                    const coordinates = e.features[0].geometry.coordinates.slice();
                    const properties = e.features[0].properties;
                    const safetyText = safetyLevels[bikePath.safetyLevel]?.text || 'Неизвестно';
                
                    // Добавляем класс в зависимости от значения safetyLevel
                    const labelClass = `bg${bikePath.safetyLevel}`;

                    const popupContent = `
                        <h3>${properties.name}</h3>
                        <p class="label ${labelClass}">${safetyText}</p>
                        <p>${properties.description}</p>
                        <div class="photos">
                            ${bikePath.photos.map(photo => `<img src="${photo}" alt="Фотография велодорожки" class="popup-photo">`).join('')}
                        </div>
                        <div class="down">
                            <button class="compliance-button">
                                <img src="src/icon/warning.svg" alt="warning">
                                <p>Пожаловаться</p>
                            </button>

                            <span>
                                <p class="w20">${properties.source}</p>
                                <p class="w20">${properties.date}</p>
                            <span>
                        </div>
                    `;

                    const popup = new mapboxgl.Popup({
                        className: 'custom-popup',
                        maxWidth: '320px'
                    })
                        .setLngLat(coordinates[0])
                        .setHTML(popupContent)
                        .addTo(map);

                    // Добавляем обработчик события для кнопки compliance
                    popup.getElement().querySelector('.compliance-button').addEventListener('click', () => {
                        window.open('https://tally.so/r/mKx66k', '_blank');
                    });

                    popup.getElement().querySelectorAll('.popup-photo').forEach((photo, index) => {
                        photo.addEventListener('click', () => {
                            openFullscreenGallery(bikePath.photos, index);
                        });
                    });
                }

                map.on('mouseenter', `bike-path-${bikePath.id}`, function () {
                    map.getCanvas().style.cursor = 'pointer';
                });

                map.on('mouseleave', `bike-path-${bikePath.id}`, function () {
                    map.getCanvas().style.cursor = '';
                });
            });
        })
        .catch(error => console.error('Ошибка загрузки данных:', error));
});

function openFullscreenGallery(photos, initialIndex) {
    const galleryContainer = document.createElement('div');
    galleryContainer.classList.add('photoview');
    galleryContainer.style.opacity = '0';
    document.body.appendChild(galleryContainer);

    let currentIndex = initialIndex;

    setTimeout(() => {
        galleryContainer.style.opacity = '1';
        galleryContainer.classList.add('visible');
    }, 10);

    function updateGalleryContent() {
        // Очищаем контейнер и добавляем текущую фотографию
        galleryContainer.innerHTML = '';
        const img = document.createElement('img');
        img.src = photos[currentIndex];
        galleryContainer.appendChild(img);

        // Отображаем номер текущей фотографии и общее количество
        const counter = document.createElement('div');
        counter.classList.add('gallery-counter');
        counter.textContent = `${currentIndex + 1}/${photos.length}`;
        galleryContainer.appendChild(counter);
        
        // Добавляем кнопку закрытия
        const closeButton = document.createElement('div');
        closeButton.classList.add('gallery-close');
        closeButton.textContent = '✕';
        galleryContainer.appendChild(closeButton);

        // Добавляем стрелку влево
        const leftArrow = document.createElement('div');
        leftArrow.classList.add('gallery-arrow', 'gallery-arrow-left');
        leftArrow.textContent = '←';
        galleryContainer.appendChild(leftArrow);

        // Добавляем стрелку вправо
        const rightArrow = document.createElement('div');
        rightArrow.classList.add('gallery-arrow', 'gallery-arrow-right');
        rightArrow.textContent = '→';
        galleryContainer.appendChild(rightArrow);

        // Обработчик события для закрытия полноэкранного просмотра
        closeButton.addEventListener('click', (e) => {
            e.stopPropagation(); // Предотвращаем распространение события на родительские элементы
            document.body.removeChild(galleryContainer);
        });

        // Обработчики событий для стрелок
        leftArrow.addEventListener('click', (e) => {
            e.stopPropagation(); // Предотвращаем распространение события на родительские элементы
            if (currentIndex > 0) {
                currentIndex--;
                updateGalleryContent();
            }
        });

        rightArrow.addEventListener('click', (e) => {
            e.stopPropagation(); // Предотвращаем распространение события на родительские элементы
            if (currentIndex < photos.length - 1) {
                currentIndex++;
                updateGalleryContent();
            }
        });
    }

    updateGalleryContent();
}
