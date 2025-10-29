/**
 * AI Robot Assistant for Coins Bot Landing Page
 * Animated assistant that guides users through the landing page
 */

class RobotAssistant {
  constructor() {
    this.robot = null;
    this.container = null;
    this.bubble = null;
    this.bubbleText = null;
    this.currentSection = 'hero';
    this.isAnimating = false;
    this.isIdle = false;
    this.idleTimer = null;
    this.speechQueue = [];
    this.visited = new Set();

    // Robot waypoints for each section
    this.waypoints = {
      hero: {
        position: { right: 100, bottom: 150 },
        animation: 'waving',
        speech: 'Привет! Я помогу тебе вести учет расходов!',
        duration: 3000
      },
      features: {
        position: { left: 50, top: '25%' },
        animation: 'pointing',
        speech: 'Посмотри на наши возможности!',
        duration: 2500
      },
      how: {
        position: { right: 80, top: '35%' },
        animation: 'thinking',
        speech: 'Всего 3 простых шага!',
        duration: 2500
      },
      demo: {
        position: { left: 100, top: '45%' },
        animation: 'pointing',
        speech: 'Попробуй демо версию!',
        duration: 3000
      },
      pricing: {
        position: { left: '50%', top: 100, transform: 'translateX(-50%)' },
        animation: 'thinking',
        speech: 'Выбери подходящий тариф!',
        duration: 3000
      },
      faq: {
        position: { right: 50, top: '30%' },
        animation: 'thinking',
        speech: 'Есть вопросы? Я отвечу!',
        duration: 2500
      },
      cta: {
        position: { left: 80, bottom: 100 },
        animation: 'celebrating',
        speech: 'Начни экономить прямо сейчас!',
        duration: 3500
      }
    };

    // Interactive hints based on user behavior
    this.hints = {
      firstVisit: 'Нажми на кнопку чтобы начать!',
      scrollDown: 'Прокрути вниз, там интересно!',
      hoverButton: 'Отличный выбор!',
      clickDemo: 'Попробуй демо версию!',
      viewPricing: 'Premium дает больше возможностей!',
      readFaq: 'Здесь ответы на все вопросы!',
      finalCta: 'Не упусти шанс - начни сейчас!'
    };

    this.init();
  }

  init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.setup());
    } else {
      this.setup();
    }
  }

  setup() {
    this.createRobot();
    this.initIntersectionObserver();
    this.initEventListeners();
    this.startIdleTimer();

    // Initial greeting
    setTimeout(() => {
      this.moveToSection('hero');
    }, 500);
  }

  createRobot() {
    // Create robot HTML structure
    const robotHTML = `
      <div id="ai-assistant" class="ai-robot interactive">
        <div class="robot-trail"></div>
        <div class="robot-container">
          <img src="robot.jpg" class="robot-body" alt="AI Assistant">
          <div class="robot-eyes">
            <div class="eye left"></div>
            <div class="eye right"></div>
          </div>
          <div class="robot-speech-bubble">
            <span class="bubble-text"></span>
          </div>
        </div>
      </div>
    `;

    // Add robot to page
    document.body.insertAdjacentHTML('beforeend', robotHTML);

    // Get references
    this.robot = document.getElementById('ai-assistant');
    this.container = this.robot.querySelector('.robot-container');
    this.bubble = this.robot.querySelector('.robot-speech-bubble');
    this.bubbleText = this.robot.querySelector('.bubble-text');
  }

  initIntersectionObserver() {
    const options = {
      root: null,
      rootMargin: '-20% 0px -20% 0px',
      threshold: 0.3
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const sectionId = entry.target.id || entry.target.className.split(' ')[0];

          // Map section classes/ids to waypoint keys
          let waypointKey = sectionId;
          if (sectionId === 'features') waypointKey = 'features';
          else if (sectionId === 'how') waypointKey = 'how';
          else if (sectionId === 'demo' || sectionId.includes('demo')) waypointKey = 'demo';
          else if (sectionId === 'pricing') waypointKey = 'pricing';
          else if (sectionId === 'faq') waypointKey = 'faq';
          else if (entry.target.classList.contains('cta-section')) waypointKey = 'cta';
          else if (entry.target.classList.contains('hero')) waypointKey = 'hero';

          if (this.waypoints[waypointKey] && this.currentSection !== waypointKey) {
            this.moveToSection(waypointKey);
          }
        }
      });
    }, options);

    // Observe all major sections
    const sections = document.querySelectorAll('.hero, .features, .how-it-works, .demo-section, .pricing, .faq, .cta-section');
    sections.forEach(section => observer.observe(section));
  }

  initEventListeners() {
    // Robot click interaction
    this.robot.addEventListener('click', (e) => {
      e.stopPropagation();
      this.handleRobotClick();
    });

    // Track CTA button hovers
    const ctaButtons = document.querySelectorAll('.btn-primary, .btn-cta');
    ctaButtons.forEach(button => {
      button.addEventListener('mouseenter', () => {
        if (this.isNearElement(button)) {
          this.speak(this.hints.hoverButton, 1500);
          this.playAnimation('pointing');
        }
      });
    });

    // Track scroll for idle detection
    let scrollTimer;
    window.addEventListener('scroll', () => {
      this.resetIdleTimer();

      // Add flying effect during scroll
      clearTimeout(scrollTimer);
      if (!this.robot.classList.contains('flying')) {
        this.robot.classList.add('flying');
      }
      scrollTimer = setTimeout(() => {
        this.robot.classList.remove('flying');
      }, 800);
    });

    // Track mouse movement for idle detection
    document.addEventListener('mousemove', () => {
      this.resetIdleTimer();
      if (this.isIdle) {
        this.wakeUp();
      }
    });

    // FAQ accordion interaction
    const faqItems = document.querySelectorAll('.faq-item');
    faqItems.forEach(item => {
      item.addEventListener('click', () => {
        if (this.currentSection === 'faq') {
          this.speak('Отличный вопрос!', 1500);
          this.playAnimation('thinking');
        }
      });
    });

    // Demo video play button
    const demoButton = document.querySelector('.demo-play-btn');
    if (demoButton) {
      demoButton.addEventListener('click', () => {
        this.speak('Смотри как это работает!', 2000);
        this.playAnimation('pointing');
      });
    }
  }

  moveToSection(sectionKey) {
    if (this.isAnimating || !this.waypoints[sectionKey]) return;

    this.isAnimating = true;
    this.currentSection = sectionKey;
    const waypoint = this.waypoints[sectionKey];

    // Add flying animation
    this.robot.classList.add('flying');

    // Move robot to new position
    this.setPosition(waypoint.position);

    // After movement animation
    setTimeout(() => {
      this.robot.classList.remove('flying');

      // Play section animation
      this.playAnimation(waypoint.animation);

      // Show speech if not visited before
      if (!this.visited.has(sectionKey)) {
        this.speak(waypoint.speech, waypoint.duration);
        this.visited.add(sectionKey);
      }

      this.isAnimating = false;
    }, 800);
  }

  setPosition(position) {
    // Reset all position styles
    this.robot.style.left = 'auto';
    this.robot.style.right = 'auto';
    this.robot.style.top = 'auto';
    this.robot.style.bottom = 'auto';
    this.robot.style.transform = '';

    // Apply new position
    Object.keys(position).forEach(key => {
      if (key === 'transform') {
        this.robot.style.transform = position[key];
      } else {
        const value = typeof position[key] === 'number' ? `${position[key]}px` : position[key];
        this.robot.style[key] = value;
      }
    });
  }

  playAnimation(animationName) {
    // Remove all animation classes
    ['waving', 'pointing', 'thinking', 'celebrating', 'flying'].forEach(anim => {
      this.robot.classList.remove(anim);
    });

    // Add new animation
    if (animationName) {
      this.robot.classList.add(animationName);

      // Remove animation class after completion
      const duration = animationName === 'celebrating' ? 1500 : 1000;
      setTimeout(() => {
        this.robot.classList.remove(animationName);
      }, duration);
    }
  }

  speak(text, duration = 3000) {
    if (!text) return;

    // Add to queue if already speaking
    if (this.bubble.classList.contains('active')) {
      this.speechQueue.push({ text, duration });
      return;
    }

    this.bubbleText.textContent = text;
    this.bubble.classList.add('active');

    setTimeout(() => {
      this.bubble.classList.remove('active');

      // Process queue
      if (this.speechQueue.length > 0) {
        const next = this.speechQueue.shift();
        setTimeout(() => this.speak(next.text, next.duration), 300);
      }
    }, duration);
  }

  handleRobotClick() {
    const clickResponses = [
      { text: 'Я твой финансовый помощник!', animation: 'waving' },
      { text: 'Попробуй Coins Bot бесплатно!', animation: 'pointing' },
      { text: 'Экономь с умом!', animation: 'thinking' },
      { text: 'Управляй расходами легко!', animation: 'celebrating' },
      { text: 'Coins Bot - это просто!', animation: 'waving' }
    ];

    const response = clickResponses[Math.floor(Math.random() * clickResponses.length)];
    this.speak(response.text, 2500);
    this.playAnimation(response.animation);
  }

  isNearElement(element) {
    const robotRect = this.robot.getBoundingClientRect();
    const elementRect = element.getBoundingClientRect();

    const distance = Math.sqrt(
      Math.pow(robotRect.left - elementRect.left, 2) +
      Math.pow(robotRect.top - elementRect.top, 2)
    );

    return distance < 200;
  }

  startIdleTimer() {
    this.idleTimer = setTimeout(() => {
      this.goToSleep();
    }, 15000); // 15 seconds
  }

  resetIdleTimer() {
    clearTimeout(this.idleTimer);
    this.startIdleTimer();
  }

  goToSleep() {
    if (!this.isIdle) {
      this.isIdle = true;
      this.robot.classList.add('sleeping');
      this.speak('Z-z-z...', 2000);
    }
  }

  wakeUp() {
    if (this.isIdle) {
      this.isIdle = false;
      this.robot.classList.remove('sleeping');
      this.speak('О, ты вернулся!', 2000);
      this.playAnimation('waving');
    }
  }

  // Public method to trigger specific behaviors
  trigger(action, data) {
    switch (action) {
      case 'speak':
        this.speak(data.text, data.duration);
        break;
      case 'animate':
        this.playAnimation(data.animation);
        break;
      case 'move':
        this.setPosition(data.position);
        break;
      case 'celebrate':
        this.playAnimation('celebrating');
        this.speak('Ура! Отличная работа!', 3000);
        break;
      default:
        break;
    }
  }
}

// Initialize robot when script loads
const coinsRobot = new RobotAssistant();