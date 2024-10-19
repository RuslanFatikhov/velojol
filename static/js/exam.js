let questions = [];
let currentQuestionIndex = 0;
let correctAnswersCount = 0;

// Функция для загрузки вопросов из exam.json
function loadQuestions() {
  fetch('/exam_data')
    .then(response => response.json())
    .then(data => {
      questions = data;
      showQuestion();
    })
    .catch(error => {
      console.error('Ошибка при загрузке вопросов:', error);
      alert('Не удалось загрузить вопросы. Пожалуйста, попробуйте позже.');
    });
}

function showQuestion() {
  const quizContainer = document.getElementById('quiz-container');

  // Обновляем счетчик вопросов
  const questionCounter = document.getElementById('question-counter');
  questionCounter.textContent = `${currentQuestionIndex + 1}/${questions.length}`;

  // Очищаем предыдущий контент, кроме счетчика
  Array.from(quizContainer.children).forEach(child => {
    if (child.id !== 'question-counter') {
      quizContainer.removeChild(child);
    }
  });

  const questionObj = questions[currentQuestionIndex];

  // Отображение вопроса
  const questionElement = document.createElement('h5');
  questionElement.className = 'center dark-prime-invert-100 mt16';
  questionElement.textContent = questionObj.question;
  quizContainer.appendChild(questionElement);

  // Отображение изображения, если оно есть
  if (questionObj.image) {
    const imageElement = document.createElement('img');
    imageElement.className = 'mt16 exam_img';
    imageElement.src = questionObj.image;
    quizContainer.appendChild(imageElement);
  }

  // Создаем элемент <span id="quiz-buttons">
  const buttonsContainer = document.createElement('span');
  buttonsContainer.className = 'column gap8 mt16 w100';
  buttonsContainer.id = 'quiz-buttons';
  quizContainer.appendChild(buttonsContainer);

  // Отображение вариантов ответов внутри <span id="quiz-buttons">
  questionObj.options.forEach((option, index) => {
    const optionButton = document.createElement('button');
    optionButton.className = 'button fs dark-prime-invert-400 size_m bold center tac';
    optionButton.textContent = option;
    optionButton.onclick = () => selectAnswer(index);
    buttonsContainer.appendChild(optionButton);
  });
}

// Функция обработки выбранного ответа
function selectAnswer(selectedIndex) {
  const questionObj = questions[currentQuestionIndex];

  // Проверка правильности ответа
  if (selectedIndex === questionObj.correctAnswer) {
    correctAnswersCount++;
  }

  currentQuestionIndex++;

  // Проверка, есть ли ещё вопросы
  if (currentQuestionIndex < questions.length) {
    showQuestion();
  } else {
    showResult();
  }
}

// Функция отображения результата
function showResult() {
  const quizContainer = document.getElementById('quiz-container');
  const resultContainer = document.getElementById('result-container');
  const resultText = document.getElementById('result-text');

  quizContainer.style.display = 'none';
  resultContainer.style.display = 'block';

  let performance = '';
  let performance_image = '';
  let story_image = '';

  if (correctAnswersCount <= 3) {
    performance = 'Плохо';
    performance_image = '/static/images/course/bad.png';
  } else if (correctAnswersCount <= 6) {
    performance = 'Удовлетворительно';
    performance_image = '/static/images/course/average.png';
  } else if (correctAnswersCount <= 9) {
    performance = 'Хорошо';
    performance_image = '/static/images/course/good.png';
  } else {
    performance = 'Отлично';
    performance_image = '/static/images/course/excellent.png';
  }

  // Определяем изображение для истории в зависимости от количества правильных ответов
  story_image = `/static/images/stories/result_${correctAnswersCount}.jpg`;

  resultText.innerHTML = `
    <img src="${performance_image}" alt="${performance}" style="max-width: 100%; height: auto;">
    <h3 class="dark-prime-invert-100 bold center">${performance}</h3>
    <p class="dark-prime-invert-200 center">Вы ответили правильно на ${correctAnswersCount} из ${questions.length} вопросов.</p>
  `;

  // Обновляем кнопку скачивания, устанавливая ссылку на нужное изображение
  const downloadButton = document.getElementById('download-button');
  if (downloadButton) {
    downloadButton.onclick = () => {
      // Создаем скрытую ссылку для скачивания
      const link = document.createElement('a');
      link.href = story_image;
      link.download = `Результат_${correctAnswersCount}_из_${questions.length}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };
  }
}

// Обработчик для кнопки "Начать заново"
const restartButton = document.getElementById('restart-button');
if (restartButton) {
  restartButton.onclick = () => {
    currentQuestionIndex = 0;
    correctAnswersCount = 0;
    document.getElementById('result-container').style.display = 'none';
    document.getElementById('quiz-container').style.display = 'block';
    showQuestion();
  };
}

// Обработчик для кнопки "Поделиться"
const shareButton = document.getElementById('share-button');
if (shareButton) {
  shareButton.onclick = () => {
    const shareButtons = document.getElementById('social-share-buttons');
    if (shareButtons) {
      shareButtons.style.display = shareButtons.style.display === 'none' ? 'grid' : 'none';
    }
  };
}

// Добавляем обработчики для кнопок социальных сетей
const socialButtons = document.querySelectorAll('.social-button');
if (socialButtons.length > 0) {
  socialButtons.forEach(button => {
    button.onclick = () => {
      const network = button.getAttribute('data-network');
      shareResult(network);
    };
  });
}

function shareResult(network) {
  const url = window.location.href;
  const text = `Я прошёл экзамен и получил результат: ${correctAnswersCount} из ${questions.length}! Попробуйте и вы: `;

  let shareUrl = '';

  switch (network) {
    case 'vk':
      shareUrl = `https://vk.com/share.php?url=${encodeURIComponent(url)}&title=${encodeURIComponent(text)}`;
      break;
    case 'facebook':
      shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}&quote=${encodeURIComponent(text)}`;
      break;
    case 'twitter':
      shareUrl = `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
      break;
    case 'telegram':
      shareUrl = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
      break;
    case 'whatsapp':
      shareUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(text + ' ' + url)}`;
      break;
    // Добавьте другие социальные сети по аналогии
    default:
      alert('Неизвестная социальная сеть');
      return;
  }

  window.open(shareUrl, '_blank');
}

// Инициализация экзамена при загрузке страницы
window.onload = loadQuestions;
