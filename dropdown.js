// Получаем кнопку и выпадающий контент
var dropdownBtn = document.getElementById("dropdownBtn");
var dropdownContent = document.getElementById("dropdownContent");

// Переключаем класс "show" при нажатии на кнопку
dropdownBtn.addEventListener("click", function(event) {
    // Отменяем стандартное действие кнопки (если оно есть)
    event.preventDefault();
    // Отменяем всплытие события
    event.stopPropagation();

    // Переключаем класс "show" для выпадающего контента
    dropdownContent.classList.toggle("show");

    // Закрываем выпадающий контент, если пользователь кликнул вне него
    function closeDropdown(event) {
        if (!event.target.matches("#dropdownBtn")) {
            dropdownContent.classList.remove("show");
            window.removeEventListener("click", closeDropdown);
        }
    }

    // Добавляем слушатель события на всё окно
    window.addEventListener("click", closeDropdown);
});

// Отменяем всплытие события для контента выпадающего меню
dropdownContent.addEventListener("click", function(event) {
    event.stopPropagation();
});
