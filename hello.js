// Получаем ссылку на попап и кнопку закрытия
const popup = document.querySelector('.hello');
const closeHelloBtn = document.getElementById('closeHelloBtn');

// Функция, чтобы показать попап
function showPopup() {
    popup.style.display = 'flex';
}

// Функция, чтобы скрыть попап
function closePopup() {
    popup.style.display = 'none';
}

// Показываем попап при загрузке страницы
window.onload = function() {
    showPopup();
};

// Закрываем попап при клике на кнопку закрытия
closeHelloBtn.addEventListener('click', closePopup);
