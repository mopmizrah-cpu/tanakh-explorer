# ממשק ה־API

השרת (`python -m tanakh_explorer serve`) מגיש JSON תחת `/api`. תיעוד אינטראקטיבי אוטומטי זמין ב־`/docs` (Swagger).
כל בקשת חיפוש היא אובייקט JSON. כל תשובה כוללת `settings`, ובו ההגדרות המדויקות שבהן בוצע החיפוש.

## שדות משותפים

| שדה | ערכים | ברירת מחדל |
|---|---|---|
| `layer` | `{"kq": "ketiv"\|"qere", "maqaf": "split"\|"join"}` | כתיב, מקף מפריד |
| `scope` | `{"items": [...]}` (ראו להלן) | כל התנ״ך |
| `finals` | `"fold"` (ם=מ) / `"exact"` | `fold` |
| `niqqud_values` | החלפת ערכים בטבלת הניקוד, למשל `{"qamats_qatan": 12}` | הטבלה של החוקר |
| `limit`, `offset` | עימוד התוצאות המוצגות (`total` תמיד מדויק) | 100, 0 |
| `save` | שמירה בהיסטוריה | `true` |

**תחום (`scope.items`):** `{"type":"all"}`, `{"type":"section","value":"torah"}`, `{"type":"books","value":["Gen"]}`,
`{"type":"group","value":"תרי עשר"}`, `{"type":"parasha","value":"נח"}`, `{"type":"masoretic","book":"Gen","number":3}`,
`{"type":"chapters","book":"Gen","from":1,"to":3}`, `{"type":"verses","from":"Gen.1.1","to":"Gen.2.3"}`.

**דילוג:** `skips: [d]` הוא דילוג קבוע; `skips: [d1, d2, …]` (k−1 ערכים) הוא דילוג משתנה. דילוג d פירושו
שהיחידות שנבחרו מרוחקות d מקומות זו מזו (d=1 = יחידות סמוכות). `anchor` (`scope`/`verse`/`chapter`) יחד עם
`anchor_skip` קובעים את מיקום האות הראשונה ביחס לנקודת התחלה.

## נקודות קצה

| שיטה | נתיב | תיאור |
|---|---|---|
| GET | `/api/meta` | ספרים, פרשות, שיטות גימטריה וחילוף (עם פרמטרים), טבלת ניקוד |
| GET | `/api/sections/{book}` | הפרשות הפתוחות והסתומות בספר |
| POST | `/api/search/letters` | `query`, `unit` (`words`/`verses`/`letters`), `selector` (`first`/`last`/`mixed` + `selectors`), `skips`, `boundary` (`none`/`word`/`verse`/`chapter`/`book`), `reverse`, `whole_word`, `letter_groups` (`articulation`), `anchor`, `anchor_skip` |
| POST | `/api/search/phrase` | מילים שלמות ברצף (עם דילוגים אפשריים) |
| POST | `/api/search/mode` | חיפוש אותיות לפי מצב בשם: `search_mode` (`word`/`sequence`/`heads`/`tails`/`verse_heads`/`verse_tails`) |
| POST | `/api/search/anagram` | כל סידורי אותיות השאילתה (עד 12 אותיות): `search_mode`, `skips`, `boundary`, `include_original`. מחזיר את ההתאמות ואת `arrangements` — טבלת הופעות לכל סידור (כל הסידורים כשיש עד 5,040; אחרת רק אלה שנמצאו). האותיות הסופיות נחשבות רגילות (ם = מ) |
| POST | `/api/search/niqqud` | `query` מנוקד, `match` (`niqqud`/`letters_niqqud`/`value`/`letters_value`), `unit`, `selector`, `whole_word`, `full_verse`, `merge_qamats_qatan` |
| POST | `/api/search/niqqud-sum` | `kind`: `word`/`heads`/`verse_heads`/`in_verse` (+`sub`: `verse_total`/`run`/`single_word`/`word_heads`/`word_tails`), `compare`: `niqqud`/`letters`, `target`, `length` |
| POST | `/api/search/gematria` | `method`, `params`, `query` או `target`, `span` (`words`/`verse`), `n_min`, `n_max`, `cross_verses` |
| POST | `/api/search/gematria-all` | ערך השאילתה בכל השיטות ומספר ההתאמות לכל שיטה |
| POST | `/api/search/transform` | `transformation`, `transform_params`, `search_mode` (`word`/`sequence`/`heads`/`tails`/`verse_heads`/`verse_tails`) |
| POST | `/api/search/transform-all` | כל החילופים וכל 21 ההזזות המחזוריות × מצב החיפוש |
| POST | `/api/search/all-combined` | כל החילופים × שיטות הגימטריה שנבחרו |
| POST | `/api/search/pipeline` | `query`, `steps` (ראו [חיפוש משולב](#חיפוש-משולב)) |
| POST | `/api/pipeline/validate` | בדיקת התאמת סוגים בין השלבים |
| POST | `/api/scan/estimate` | אומדן היקף הסריקה: מספר תבניות הדילוג × מספר נקודות ההתחלה, ואומדן מספר ההתאמות |
| POST | `/api/scan/start` | פתיחת משימת סריקה (`skip_min`, `skip_max`, `variable`) → `job_id` |
| GET/POST | `/api/jobs`, `/api/jobs/{id}`, `/api/jobs/{id}/cancel`, `/api/jobs/{id}/resume` | מצב המשימה, ביטול וחידוש מנקודת השמירה |
| POST | `/api/calc/gematria`, `/api/calc/transform`, `/api/calc/shifts`, `/api/calc/letters` | מחשבונים |
| POST | `/api/stats/table`, `/api/stats/cell`, `/api/stats/distribution`, `/api/stats/compare`, `/api/stats/summary` | ניתוח אותיות וניקוד |
| GET | `/api/reader/{book}/{chapter}` | פרק להצגה |
| GET/POST | `/api/validation`, `/api/validation/run` | דוח התקינות |
| GET/DELETE | `/api/history`, `/api/history/{id}`, `/api/history/{id}/export?format=csv\|json` | היסטוריה וייצוא |
| POST/DELETE | `/api/custom-methods`, `/api/custom-methods/{slug}` | שיטות גימטריה מותאמות אישית |

## חיפוש משולב

כל שלב מקבל סוג קלט מסוים ומפיק סוג פלט מסוים. שלב שאינו תואם לשלב הקודם נדחה עם הסבר, ואין המרה סמויה בין סוגים.

| פעולה | קלט → פלט | פרמטרים |
|---|---|---|
| `transform` | טקסט → טקסט | `transformation`, `params` |
| `custom_map` | טקסט → טקסט | `map` |
| `heads` / `tails` | טקסט → טקסט | — |
| `gematria` | טקסט → מספר | `method`, `params`, `include_niqqud` |
| `add_niqqud` | טקסט → מספר | — |
| `arith` | מספר → מספר | `operator` (`+`/`*`), `value` |
| `search_text` | טקסט → התאמות | `search_mode` או שדות `search/letters` |
| `search_niqqud` | טקסט → התאמות | שדות `search/niqqud` |
| `search_value` | מספר → התאמות | `method`, `n_min`, `n_max`, `span` |

דוגמה: `{"query":"שָׁלוֹם","steps":[{"op":"transform","transformation":"atbash"},{"op":"gematria","method":"kidmi","include_niqqud":true},{"op":"search_value","method":"standard"}]}`
