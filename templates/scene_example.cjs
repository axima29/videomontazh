// Пример сцены записи экрана. Время в S.at(t) - время РИЛСА: курсор делает то, о чем автор говорит в эту секунду.
// Время слов берется из reels/<rid>/data.js (поле words) после prep.py --stage data.
// Запись: node scripts/rec.cjs screen/scenes/search.cjs, потом python3 scripts/resample.py search --clips screen/clips
module.exports = {
  name: 'search',          // папка клипа: screen/clips/search
  t0: 15.3,                // с какого момента рилса сцена в кадре (берите на 0,1-0,3 с раньше первого слова сцены)
  dur: 7.1,                // сколько секунд писать
  url: '/docs/work',       // относительно BASE_URL, или полный адрес (file:// для статической страницы)
  // вход в демо-копию до записи (необязательно). Пароль только демо-копии, держать в переменной окружения
  async login(p, B) {
    await p.goto(B + '/login');
    if (await p.locator('form.login').count()) {
      await p.fill('input[name=user]', process.env.DEMO_USER || 'demo');
      await p.fill('input[type=password]', process.env.DEMO_PASS || '');
      await p.click('button[type=submit]'); await p.waitForLoadState('networkidle');
    }
  },
  // подготовка до записи (необязательно): открыть нужное состояние, чтобы в кадре не было лишних шагов
  async prep(S) { await S.p.waitForTimeout(500); },
  async run(S) {
    const p = S.p;
    await S.at(15.35); await S.click('button[aria-label=Поиск]', 300);       // слово "давайте напишу"
    await S.at(15.95); await S.type('карточки', 55);                          // слово "карточки"
    await S.at(16.95); await p.keyboard.press('Enter');
    await S.at(18.85); await S.glide(p.getByText('Раздел').first(), 450, 0, 22);   // "только этот раздел"
    await S.at(20.0); await S.glide(p.getByText('Автор').first(), 400, 0, 22);     // "конкретный автор"
    await S.at(20.7); await S.click(p.getByText('За неделю').first(), 350);         // "за неделю"
    await S.glide([300, 520], 500);                                                  // точка в css-пикселях окна 540x960
  },
};
