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
    
    animateCityCards();

    const cityRequestModal = document.getElementById('cityRequestModal');
    const openCityRequestModal = document.getElementById('openCityRequestModal');
    const closeCityRequestModal = document.getElementById('closeCityRequestModal');
    const cityRequestInput = document.getElementById('cityRequestInput');

    function closeRequestModal() {
        if (!cityRequestModal) return;
        cityRequestModal.hidden = true;
        cityRequestModal.style.display = 'none';
        openCityRequestModal?.setAttribute('aria-expanded', 'false');
        openCityRequestModal?.focus();
    }

    openCityRequestModal?.addEventListener('click', function(event) {
        event.preventDefault();
        cityRequestModal.hidden = false;
        cityRequestModal.style.display = 'flex';
        openCityRequestModal.setAttribute('aria-expanded', 'true');
        cityRequestInput?.focus();
    });

    closeCityRequestModal?.addEventListener('click', closeRequestModal);

    cityRequestModal?.addEventListener('click', function(event) {
        if (event.target === cityRequestModal) {
            closeRequestModal();
        }
    });

    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && cityRequestModal && !cityRequestModal.hidden) {
            closeRequestModal();
        }
    });
});

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
