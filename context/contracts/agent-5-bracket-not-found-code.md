# Запрос A5 → A4: код ошибки `bracket_not_found`

- Автор: Агент 5 (frontend), 2026-10-10.
- Подпункт: P5-03a / P2-02, admin страница «Сетка и матчи».
- Текущее поведение (проверено на `develop` `a608326`, локальный backend): `GET /api/v1/tournaments/{id}/bracket` до генерации сетки отвечает `404` с телом `{"error":{"code":"not_found","message":"Not found.","fields":null}}`. В `backend/apps/competition/views.py` задано сообщение «Сетка турнира ещё не создана.», но итоговый envelope его заменяет общим `Not found.`.
- Контракт: [agent-4-match-ui.md](agent-4-match-ui.md) п. 3 — код `bracket_not_found` (допустимо `bracket_not_generated`).
- Предложение: `TournamentBracketView.get` возвращает envelope с `code: "bracket_not_found"` и русским `message`. Остальные 404 (неизвестный турнир, не участник) остаются `not_found`.
- Потребители: только frontend, `frontend/src/pages/AdminMatchPage.tsx`.
- Совместимость: изменение additive для клиентов, понимающих оба кода. Frontend уже принимает `bracket_not_found`, `bracket_not_generated` и `not_found`.
- Временное решение A5 (не блокирует работу): при 404 на bracket сразу после успешного чтения самого турнира frontend считает, что сетка не создана, и показывает кнопку генерации. Если исчезнет сам маршрут, ошибка проявится при попытке генерации, а не при загрузке страницы. После выпуска нового кода `not_found` можно убрать из списка принимаемых.
