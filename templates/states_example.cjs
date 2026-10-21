// Состояния продукта для мокапов (scripts/mock_shots.cjs): одно состояние = один кадр мокапа.
// cursor - где нарисовать курсор: там, куда в этой сцене будем нажимать (по нему видно, не закрывает ли его фигура автора).
module.exports = {
  async login(p, B) { /* как в сцене записи */ },
  states: {
    search: {url: '/docs/work', async run(p) {
      await p.click('button[aria-label=Поиск]'); await p.keyboard.type('карточки'); await p.keyboard.press('Enter'); await p.waitForTimeout(1500); },
      cursor: p => p.locator('mark').first()},
    history: {url: '/docs/page', async run(p) { await p.mouse.click(472, 28); await p.getByText('История изменений').click(); },
      cursor: p => p.getByText('История изменений').first()},
  },
};
