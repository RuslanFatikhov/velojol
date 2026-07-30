/**
 * Основные скрипты для всего приложения OPEN-VELOJOL
 */

/**
 * Переключение пользовательского меню
 */
function toggleUserMenu() {
    const dropdown = document.getElementById('userDropdown');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

/**
 * Инициализация обработчиков событий для пользовательского меню
 */
function initUserMenu() {
    // Закрытие меню при клике вне его
    document.addEventListener('click', function(event) {
        const userMenu = document.querySelector('.user-menu');
        const dropdown = document.getElementById('userDropdown');
        
        if (userMenu && dropdown && !userMenu.contains(event.target)) {
            dropdown.classList.remove('show');
        }
    });
}

/**
 * Автоматическое скрытие flash-сообщений
 */
function initFlashMessages() {
    setTimeout(function() {
        const flashMessages = document.querySelectorAll('.flash-message');
        
        flashMessages.forEach(function(message) {
            message.style.opacity = '0';
            message.style.transform = 'translateY(-10px)';
            message.style.transition = 'opacity 0.5s, transform 0.5s';
            
            setTimeout(function() {
                message.remove();
            }, 500);
        });
    }, 5000); // Скрываем через 5 секунд
}

/**
 * Инициализация всех общих компонентов
 */
function initMainApp() {
    initUserMenu();
    initFlashMessages();
}

// Запускаем инициализацию после загрузки DOM
document.addEventListener('DOMContentLoaded', initMainApp);
