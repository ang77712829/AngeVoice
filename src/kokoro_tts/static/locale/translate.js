(function () {
  var storageKey = 'angevoice.locale.v1';
  var aliases = {
    'zh': 'zh-CN',
    'zh-cn': 'zh-CN',
    'zh-CN': 'zh-CN',
    'en': 'en',
    'en-us': 'en',
    'en-US': 'en'
  };

  function available(locale) {
    return Boolean(window.AngeVoiceLocales && window.AngeVoiceLocales[locale]);
  }

  function normalize(locale) {
    var key = aliases[String(locale || '').trim()] || 'zh-CN';
    return available(key) ? key : 'zh-CN';
  }

  function currentLocale() {
    var saved = localStorage.getItem(storageKey);
    return normalize(saved || navigator.language || 'zh-CN');
  }

  function render(key, params, locale) {
    var lang = normalize(locale || currentLocale());
    var messages = (window.AngeVoiceLocales && window.AngeVoiceLocales[lang]) || {};
    var fallback = (window.AngeVoiceLocales && window.AngeVoiceLocales['zh-CN']) || {};
    var template = messages[key] || fallback[key] || key;
    Object.keys(params || {}).forEach(function (name) {
      template = template.replaceAll('{' + name + '}', String(params[name]));
    });
    return template;
  }

  function applyNode(node, locale) {
    if (node.dataset.i18n) {
      node.textContent = render(node.dataset.i18n, null, locale);
    }
    if (node.dataset.i18nHtml) {
      node.innerHTML = render(node.dataset.i18nHtml, null, locale);
    }
    if (node.dataset.i18nPlaceholder) {
      node.setAttribute('placeholder', render(node.dataset.i18nPlaceholder, null, locale));
    }
    if (node.dataset.i18nTitle) {
      var value = render(node.dataset.i18nTitle, null, locale);
      node.setAttribute('title', value);
      node.setAttribute('aria-label', value);
    }
  }

  function apply(locale) {
    var lang = normalize(locale);
    localStorage.setItem(storageKey, lang);
    document.documentElement.lang = lang;
    document.documentElement.dataset.locale = lang;
    document.querySelectorAll('[data-i18n],[data-i18n-html],[data-i18n-placeholder],[data-i18n-title]').forEach(function (node) {
      applyNode(node, lang);
    });
    document.querySelectorAll('[data-locale-choice]').forEach(function (node) {
      node.classList.toggle('active', node.dataset.localeChoice === lang);
    });
    document.querySelectorAll('[data-current-locale]').forEach(function (node) {
      node.textContent = render('language.current', null, lang);
    });
    document.dispatchEvent(new CustomEvent('angevoice:locale-changed', { detail: { locale: lang } }));
  }

  function bind() {
    document.querySelectorAll('[data-locale-choice]').forEach(function (node) {
      node.addEventListener('click', function (event) {
        event.preventDefault();
        event.stopPropagation();
        apply(node.dataset.localeChoice || 'zh-CN');
        var menu = node.closest('[data-locale-menu]');
        if (menu) menu.open = false;
      });
    });
    document.querySelectorAll('[data-locale-menu]').forEach(function (node) {
      node.addEventListener('toggle', function () {
        if (node.open) {
          document.querySelectorAll('[data-locale-menu]').forEach(function (other) {
            if (other !== node) other.open = false;
          });
        }
      });
    });
    document.addEventListener('click', function (event) {
      document.querySelectorAll('[data-locale-menu]').forEach(function (node) {
        if (node.open && !node.contains(event.target)) {
          node.open = false;
        }
      });
    });
    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape') return;
      document.querySelectorAll('[data-locale-menu]').forEach(function (node) {
        node.open = false;
      });
    });
  }

  window.AngeVoiceI18n = {
    t: render,
    apply: apply,
    locale: currentLocale
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      bind();
      apply(currentLocale());
    });
  } else {
    bind();
    apply(currentLocale());
  }
}());
