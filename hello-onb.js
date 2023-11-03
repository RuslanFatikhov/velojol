
  var container = document.getElementById('lottie-animation');

  // Указываете путь к вашему файлу JSON
  var animationPath = 'onb.json';

  // Загружаем и проигрываем анимацию
  lottie.loadAnimation({
    container: container, // Ссылка на контейнер
    renderer: "svg", // Выберите 'svg', 'canvas' или 'html' (по умолчанию - 'svg')
    loop: true, // Повторять анимацию или нет
    autoplay: true, // Автоматически начать проигрывание при загрузке
    path: animationPath // Путь к вашему файлу JSON
  });
