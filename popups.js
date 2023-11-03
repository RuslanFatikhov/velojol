// Получаем кнопки и попапы
const aboutBtn = document.getElementById('aboutBtn');
const donateBtn = document.getElementById('donateBtn');
const cityBtn = document.getElementById('cityBtn');
const changeBtn = document.getElementById('changeBtn');

const aboutPopup = document.getElementById('aboutPopup');
const donatePopup = document.getElementById('donatePopup');
const cityPopup = document.getElementById('cityPopup');
const changePopup = document.getElementById('changePopup');



// Функции для открытия и закрытия попапов с анимацией
function openPopup(popup) {
    popup.classList.add('active');
}

function closePopup(popup) {
    popup.classList.remove('active');
}

// Назначаем обработчики событий
aboutBtn.addEventListener('click', () => openPopup(aboutPopup));
donateBtn.addEventListener('click', () => openPopup(donatePopup));
cityBtn.addEventListener('click', () => openPopup(cityPopup));
changeBtn.addEventListener('click', () => openPopup(changePopup));

// Назначаем обработчики событий для закрытия попапов
const closeAboutBtn = document.getElementById('closeAboutBtn');
const closeDonateBtn = document.getElementById('closeDonateBtn');
const closeCityBtn = document.getElementById('closeCityBtn');
const closeChangeBtn = document.getElementById('closeChangeBtn');
const popups = document.querySelectorAll('.popup');

closeAboutBtn.addEventListener('click', () => closePopup(aboutPopup));
closeDonateBtn.addEventListener('click', () => closePopup(donatePopup));
closeCityBtn.addEventListener('click', () => closePopup(cityPopup));
closeChangeBtn.addEventListener('click', () => closePopup(changePopup));

// Закрываем попапы, если пользователь кликает за пределами них
popups.forEach(popup => {
    popup.addEventListener('click', (event) => {
        if (event.target === popup) {
            closePopup(popup);
        }
    });
});
