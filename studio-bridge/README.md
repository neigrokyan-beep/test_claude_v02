# Studio Bridge — Cinema 4D, Houdini, Fusion, Nuke, Obsidian и библиотека GSG для Claude из облака

Облачная сессия Claude не видит твой ПК. Studio Bridge решает это так:

```
claude.ai (облако) ──HTTPS──► туннель (cloudflared / ngrok) ──► gateway.py на ПК (127.0.0.1:8765)
                                                                  ├─ cinema4d-mcp ─► плагин в C4D   (порт 5555)
                                                                  ├─ houdini-mcp  ─► модуль в Houdini (порт 9876)
                                                                  └─ fusion-studio-mcp ─► Fusion Studio (fusionscript)
```

`gateway.py` запускает три MCP-сервера и отдаёт их инструменты одним адресом
(`c4d__…`, `houdini__…`, `fusion__…` плюс `bridge_status`). Этот адрес
добавляется в claude.ai как **один** пользовательский коннектор.

Используемые MCP-серверы (ставятся автоматически в `apps/`):

| Программа | Сервер |
|---|---|
| Cinema 4D | [ttiimmaacc/cinema4d-mcp](https://github.com/ttiimmaacc/cinema4d-mcp) |
| Houdini | [eetumartola/houdini-mcp](https://github.com/eetumartola/houdini-mcp) |
| Fusion Studio | [bigsbypuglise/fusion-studio-mcp](https://github.com/bigsbypuglise/fusion-studio-mcp) |
| Nuke | [kleer001/nuke-mcp](https://github.com/kleer001/nuke-mcp) (панель NukeMCP в Nuke, порт 54321) |
| Obsidian + библиотека GSG | свой сервер `weaver-server/` (ниже) |

## Weaver: хранилище Obsidian и библиотека материалов GSG

Сервер `weaver-server/weaver_server.py` (инструменты `weaver__…`) даёт облачной сессии то же, что локальному
Claude Code на ПК. Пути по умолчанию: хранилище `G:\todoist_obsidian_claude`, библиотека
`E:\assets\Greyscalegorilla Studio\assets\Greyscalegorilla_Library`. Если у тебя другие:
`install.cmd -Vault "X:\..." -Gsg "X:\..."`.

| Инструменты | Что делают |
|---|---|
| `weaver_context` | вход в хранилище: `CLAUDE.md` с START, STATE, MAP, PROJECTS |
| `vault_list` · `vault_read` · `vault_search` | смотреть папки, читать и искать по заметкам и скриптам |
| `vault_write` | создать, дописать или перезаписать текстовый файл; перед перезаписью старая версия уходит в `Agent/History/<дата>/`; удалять нельзя |
| `view_image` | посмотреть картинку из хранилища или библиотеки |
| `gsg_stats` · `gsg_guide` · `gsg_find` · `gsg_collection` · `gsg_sheet` | обзор библиотеки, твой гайд «что где», поиск по названию, коллекция целиком, листы превью |
| `gsg_preview` · `gsg_show` · `gsg_reindex` | превью ассета; карточка: карты по разрешениям с цветовым пространством, параметры Standard Surface, пути; пересканировать библиотеку |

Защита: библиотека только для чтения. Из облака нельзя писать в `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.agents/`,
`Agent/Scripts/`, `STATE.md`, `PROJECTS.md`, `Eagle_lib/`, `.obsidian/`, `.git/`: это файлы, которыми управляется
локальный агент на ПК, и записать в них чужое значило бы дать команды программе с доступом к оболочке.

## 1. Установка (один раз)

Нужны: Windows 10/11, [Git](https://git-scm.com) и Python 3.11+.
```
winget install Git.Git
winget install Python.Python.3.12
```

Скачай репозиторий (или папку `studio-bridge`) и запусти **`install.cmd`**.
Скрипт:

- поставит gateway и три MCP-сервера, каждый в свой venv;
- скопирует плагин C4D в `%APPDATA%\Maxon\<версия>\plugins\cinema4d-mcp\`;
- положит `houdini_mcp.py` в `Documents\houdiniXX.X\pythonX.Ylibs\` и добавит полку **Studio Bridge**;
- найдёт `fusionscript.dll` (если не найдёт: `install.cmd -FusionDll "C:\...\fusionscript.dll"`);
- скачает `cloudflared.exe`;
- создаст `gateway\servers.json` со случайным токеном.

C4D и Houdini лучше хотя бы раз запустить **до** установки, чтобы у них уже были папки настроек.
Повторный запуск `install.cmd` безопасен: он обновит серверы и сохранит токен.

## 2. Каждый раз перед работой

1. **Cinema 4D**: перезапусти после установки, потом *Extensions → Socket Server Plugin → Start Server*.
2. **Houdini**: на панели полок нажми «+» → *Shelves* → **Studio Bridge**, затем кнопку **MCP Start**.
3. **Fusion Studio**: просто открой программу (нужна именно Studio: бесплатная версия не даёт внешних скриптов).
   Если подключение не проходит: *Fusion → Preferences → Global → Script* — разреши локальные скриптовые подключения.
4. Запусти **`start.cmd`**. Он покажет строку вида
   `https://xxxx.trycloudflare.com/<токен>/mcp` и скопирует её в буфер обмена.
5. Добавь коннектор: [claude.ai → Settings → Connectors](https://claude.ai/customize/connectors) →
   *Add custom connector* → вставь URL, без авторизации.
6. Открой **новую** сессию Claude (коннекторы подхватываются при старте) и попроси
   вызвать `bridge_status`. Там должно быть `c4d: ok`, `houdini: ok`, `fusion: ok`.

Открытые программы можно подключать в любом порядке. Gateway сам переподключается
к упавшим серверам.

### Постоянный адрес

Быстрый туннель Cloudflare бесплатный и работает без аккаунта, но **адрес меняется при каждом запуске**,
поэтому коннектор придётся каждый раз обновлять. С постоянным адресом так делать не нужно:

- **ngrok** (бесплатно даёт один статический домен):
  `winget install ngrok.ngrok`, затем `ngrok config add-authtoken <твой токен>`
  и `start.cmd -NgrokDomain имя.ngrok-free.app`.
- Свой туннель (например, именованный Cloudflare Tunnel) направь на `http://127.0.0.1:8765`
  и запусти `start.cmd -PublicUrl https://mcp.твой-домен`.

## Безопасность — прочитай

- Через этот коннектор можно выполнять **любой Python-код** в C4D, Houdini и Fusion, то есть фактически на твоём ПК.
- Защищает только случайный токен в URL. **Никому не показывай URL** и не коммить `gateway\servers.json`
  (он в `.gitignore`).
- Если URL утёк, удали `gateway\servers.json` и снова запусти `install.cmd`: получишь новый токен.
- Когда не работаешь, закрывай `start.cmd`, и туннель пропадёт.
- Перед работой сохраняй сцены: инструменты меняют открытые файлы.

## Диагностика

| Симптом | Что проверить |
|---|---|
| `c4d: DOWN` или ошибки подключения к 5555 | запущен ли Socket Server в C4D |
| `houdini: DOWN` / connection refused 9876 | нажата ли кнопка **MCP Start** в Houdini |
| `fusion`: `fusionscript.dll not found` | `install.cmd -FusionDll "…\fusionscript.dll"` |
| `fusion`: не находит Fusion | открыт ли Fusion **Studio**, настройки скриптов (п. 3) |
| claude.ai не принимает коннектор | открыт ли `start.cmd`; адрес туннеля мог смениться (см. `connector-url.txt`) |

Логи лежат в `logs\` (`gateway.log`, `tunnel.log`).

## Что чинит установщик

- `patches/patch_houdini.py` (запускает `install.ps1`): клиент Houdini-моста переподключается и повторяет команду,
  если сокет оборван (первый вызов после простоя давал WinError 10053/10054); `execute_houdini_code` возвращает
  ответ плагина, а не только «выполнено».
- Шлюз не передаёт `outputSchema` инструментов: иначе клиент отвергал текстовые ответы (ошибки, таймауты) Nuke.
- `watchdog/watchdog.py` перезапускает зависшие Houdini и C4D и шлюз; не хочешь, чтобы он трогал программу, —
  положи `skip_c4d.flag` или `skip_houdini.flag` (и `watchdog.hold` для полной паузы) в папку `Passes/test` задачи Watch_assembly.
- Houdini падает, если создать `redshift_vopnet` через мост или вызвать `hou.hipFile.clear()` при неподходящем драйвере OpenGL:
  каждую сцену собирай в свежей сессии и сохраняй в свой `.hiplc`.

## Проверка gateway без программ

```
gateway\.venv\Scripts\python.exe gateway\gateway.py --config gateway\servers.json
```
Адрес `http://127.0.0.1:8765/<токен>/mcp` можно открыть любым MCP-клиентом,
например `npx @modelcontextprotocol/inspector`.
