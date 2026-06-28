(function () {
  function bootstrap() {
    try {
      return JSON.parse(document.getElementById('angevoice-bootstrap')?.textContent || '{}');
    } catch (_) {
      return {};
    }
  }

  function t(key) {
    return window.AngeVoiceI18n?.t?.(key) || key;
  }

  function render() {
    var data = bootstrap();
    var banner = document.getElementById('security-banner');
    var message = document.getElementById('security-banner-message');
    if (!banner) return;
    var active = Boolean(data.adminDefaultCredentialsActive);
    banner.hidden = !active;
    if (active && message) {
      message.textContent = data.adminSecurityWarning || t('security.default_desc');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
  document.addEventListener('angevoice:locale-changed', render);
}());
