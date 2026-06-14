/**
 * Скрипт для страницы списка городов
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Инициализация страницы городов');
    
    const searchInput = document.querySelector('.search-input');
    
    if (searchInput) {
        searchInput.focus();
        
        // Живой поиск при вводе
        searchInput.addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase().trim();
            filterCities(query);
        });
    }
    
    initBusLanesBanner();
    animateCityCards();
});

function setBusLanesBannerAnswered(banner) {
    const actions = banner.querySelector('[data-banner-actions]');
    if (!actions) {
        return;
    }

    banner.classList.add('is-answered');
    actions.innerHTML = '<span class="bus-lanes-banner__thanks">Спасибо!</span>';
}

function setBusLanesBannerButtonsDisabled(banner, disabled) {
    banner
        .querySelectorAll('[data-banner-answer]')
        .forEach((button) => {
            button.disabled = disabled;
        });
}

async function initBusLanesBanner() {
    const banner = document.getElementById('bus-lanes-banner');
    if (!banner) {
        return;
    }

    try {
        const response = await fetch('/api/banner/bus-lanes');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        if (!data.show) {
            return;
        }

        banner.hidden = false;
    } catch (error) {
        console.error('Ошибка проверки баннера автобусных полос:', error);
        return;
    }

    banner.addEventListener('click', async function(event) {
        const button = event.target.closest('[data-banner-answer]');
        if (!button || button.disabled) {
            return;
        }

        const answer = button.dataset.bannerAnswer;
        setBusLanesBannerButtonsDisabled(banner, true);

        try {
            const response = await fetch('/api/banner/bus-lanes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ answer })
            });

            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }

            setBusLanesBannerAnswered(banner);
        } catch (error) {
            console.error('Ошибка отправки ответа на баннер:', error);
            setBusLanesBannerButtonsDisabled(banner, false);
        }
    });
}

/**
 * Фильтрация городов по поисковому запросу
 */
function filterCities(query) {
    const countrySections = document.querySelectorAll('.country-section');
    const emptyState = document.getElementById('emptyState');
    let visibleCitiesCount = 0;
    
    countrySections.forEach(section => {
        const cities = section.querySelectorAll('.city-card');
        let visibleInSection = 0;
        
        cities.forEach(city => {
            const cityName = city.querySelector('.city-name').textContent.toLowerCase();
            const countryName = section.querySelector('.country-name').textContent.toLowerCase();
            
            if (cityName.includes(query) || countryName.includes(query) || query === '') {
                city.style.display = 'block';
                visibleInSection++;
                visibleCitiesCount++;
            } else {
                city.style.display = 'none';
            }
        });
        
        if (visibleInSection === 0) {
            section.style.display = 'none';
        } else {
            section.style.display = 'block';
        }
    });
    
    // Показываем/скрываем empty state
    if (visibleCitiesCount === 0 && query !== '') {
        emptyState.style.display = 'block';
    } else {
        emptyState.style.display = 'none';
    }
    
    updateCitiesCount(visibleCitiesCount);
}

function updateCitiesCount(count) {
    const countElement = document.querySelector('.cities-count');
    if (countElement) {
        const word = count === 1 ? 'город' : count < 5 ? 'города' : 'городов';
        countElement.textContent = `${count} ${word}`;
    }
}

function animateCityCards() {
    const cards = document.querySelectorAll('.city-card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            setTimeout(() => {
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, 50);
        }, index * 50);
    });
}
