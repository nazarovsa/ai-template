# Frontend Template — структура каталогов и правила реализации

Шаблон и базовые правила для Next.js-фронтенда (App Router + TypeScript + TanStack Query +
Tailwind + next-intl). Извлечён из рабочего проекта `caviar-frontend`; предназначен для
копирования в новые проекты как стартовый свод правил (положить в корень фронтенда,
подключить в `CLAUDE.md` / `AGENTS.md` проекта).

Документ описывает **три вещи**:
1. эталонное дерево каталогов и назначение каждого файла;
2. правила слоёв и зависимостей (что откуда можно импортировать);
3. пошаговые чеклисты типовых задач + список анти-паттернов, которые уже стоили крови.

---

## 1. Стек

| Слой | Технология | Замечание |
|---|---|---|
| Фреймворк | Next.js 14 App Router | RSC по умолчанию, `"use client"` — точечно |
| Язык | TypeScript, `strict: true` | `noEmit`, проверка типов через `next build` |
| Данные | TanStack Query v5 | единственный источник серверного состояния |
| HTTP | axios через сгенерированный клиент | клиент генерируется из OpenAPI, руками не правится |
| Стили | Tailwind CSS + CSS-переменные | SCSS-модули — только для сложных анимаций |
| UI-примитивы | shadcn-подход (Radix + CVA) | лежат в `shared/ui`, не в `components/` |
| i18n | next-intl (`[locale]`-сегмент + middleware) | ключи типизированы из `messages/en.json` |
| Иконки | lucide-react + собственные в `shared/icons` | |

Скрипты (`package.json`):

```
dev       next dev -p <port>       # локальная разработка
build     next build               # ОН ЖЕ проверка типов — считается «сборка зелёная»
start     next start -p <port>     # прод-режим
lint      next lint
generate  node generate-api.js     # регенерация API-клиента из swagger
```

Задача считается выполненной только при зелёном `npm run build` (типы + сборка).

---

## 2. Эталонное дерево каталогов

```
<frontend>/
├── app/                          # ТОЛЬКО маршрутизация Next.js
│   ├── globals.css               # tailwind-директивы, CSS-переменные темы, глобальные keyframes
│   ├── favicon.ico
│   └── [locale]/
│       ├── layout.tsx            # <html>, шрифт, провайдеры, Toaster, #modal-root
│       ├── page.tsx              # страница «/» — только композиция + префетч
│       ├── <route>/page.tsx      # прочие маршруты
│       └── <route>/[id]/page.tsx # динамические маршруты
│
├── entities/                     # ДОМЕННЫЕ СУЩНОСТИ: доступ к данным + доменные правила
│   └── <entity>/
│       ├── service/<entity>Service.ts   # query-keys, useQuery/useMutation, prefetch
│       ├── model/                       # чистые доменные функции и константы (опционально)
│       └── ui/                          # представление самой сущности (опционально, редко)
│
├── features/                     # ПОЛЬЗОВАТЕЛЬСКИЕ СЦЕНАРИИ
│   └── <feature>/
│       ├── index.ts(x)           # публичный API фичи (barrel) — единственная точка входа извне
│       ├── components/           # компоненты фичи
│       ├── hooks/                # хуки-оркестраторы сценария
│       ├── lib/                  # чистые функции фичи (мапперы ошибок, билдеры payload)
│       ├── model/                # константы/типы сценария
│       ├── config/               # продуктовые «крутилки» (пороги, тиры, тарифы)
│       └── types/
│
├── shared/                       # ПЕРЕИСПОЛЬЗУЕМОЕ, без знания о домене
│   ├── api/
│   │   ├── generated/            # АВТОГЕНЕРАЦИЯ — не редактировать руками
│   │   └── instance.ts           # единственный HttpClient + интерсепторы + экспорт api-объектов
│   ├── ui/                       # презентационные примитивы (button, input, modal, loader, toast)
│   ├── hooks/                    # общие хуки (use-modal, use-toast, платформенные SDK)
│   ├── icons/                    # собственные SVG-компоненты
│   ├── utils/                    # чистые утилиты (формат чисел, время, cookies)
│   ├── constants/                # env, магические числа, справочники
│   ├── config/                   # конфигурация приложения (locales и т.п.)
│   └── types/                    # глобальные декларации и общие типы
│
├── lib/utils.ts                  # cn() = clsx + tailwind-merge (требование shadcn)
├── i18n/{routing.ts,request.ts}  # конфиг next-intl
├── messages/{en,ru}.json         # словари переводов
├── public/                       # статика: assets/, манифесты
├── middleware.ts                 # locale-middleware + matcher
├── next.config.mjs               # rewrites на бэкенд, заголовки кэша, плагин next-intl
├── tailwind.config.ts            # content-пути по ВСЕМ слоям, тема через CSS-переменные
├── tsconfig.json                 # paths: {"@/*": ["./*"]}
├── components.json               # конфиг shadcn (alias ui → @/shared/ui)
├── generate-api.js               # генерация клиента из OpenAPI
├── Dockerfile                    # build-args для NEXT_PUBLIC_*
└── README.md                     # env-таблица, локальный запуск, сборка образа
```

Каталогов `components/`, `pages/`, `src/` — нет. Всё, что похоже на «общие компоненты»,
живёт в `shared/ui`; всё, что относится к сценарию, — в `features/<feature>/components`.

---

## 3. Слои и правило зависимостей

```
app  →  features  →  entities  →  shared
                  ↘_____________↗
```

| Слой | Может импортировать | Категорически нельзя |
|---|---|---|
| `app` | `features`, `shared`, `entities` (только для префетча) | верстать бизнес-UI прямо в `page.tsx` |
| `features` | `entities`, `shared`, другие фичи **только через их `index`** | импортировать `app` |
| `entities` | `shared`, другие `entities` (для инвалидации ключей) | импортировать `features` |
| `shared` | только `shared` и внешние пакеты | импортировать `features`/`entities`/домен |

Дополнительно:
- **Только абсолютные импорты** через `@/…`. Относительные `../../` между слоями запрещены;
  внутри одного модуля допустимы `./`.
- Импорт внутрь чужой фичи (`@/features/x/components/y`) запрещён — только `@/features/x`.
  Поэтому у каждой фичи, которую используют снаружи, обязан быть `index.ts` с явным ре-экспортом.
- `shared/ui` не имеет права знать про домен. Если компоненту нужен `farm`/`user` — это
  компонент фичи, а не `shared`.
- Циклы между `entities` допускаются только на уровне query-keys (инвалидация чужих ключей),
  не на уровне типов и не на уровне UI.

---

## 4. `app/` — маршрутизация

Правила:
1. `page.tsx` — **тонкий**: получить параметры, при необходимости выполнить префетч, отрендерить
   компонент-экран из `features/<feature>`. Логики и вёрстки в нём нет.
2. По умолчанию страница — серверный компонент. `"use client"` в `page.tsx` — исключение,
   которое нужно обосновать; правильнее вынести клиентскую часть в `features` и оставить
   страницу серверной.
3. **Никогда не писать `"use server"` в файле страницы.** Это директива модуля Server Actions,
   а не «сделать серверным»; страницы серверные и без неё.
4. Префетч + гидратация — единственный разрешённый способ отдать данные клиенту с сервера:

```tsx
export default async function Page() {
  const queryClient = new QueryClient();
  await prefetchFarmData(queryClient);          // функция живёт в entities/*/service
  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <FarmScreen />                            // экран из features/*
    </HydrationBoundary>
  );
}
```

`QueryClient` в серверном компоненте создаётся **на каждый запрос** — не выносить в модульный
скоуп (утечка данных между пользователями).

5. `layout.tsx` локали отвечает ровно за: валидацию локали (`notFound()` для неизвестной),
   загрузку сообщений, шрифт, `NextIntlClientProvider`, композитный провайдер, `<Toaster />`
   и контейнер порталов `<div id="modal-root" />`.
   **Контракт:** `shared/ui/modal` монтируется в `#modal-root` — если убрать этот div, модалки
   упадут в рантайме.
6. Метаданные — через экспорт `metadata` в `layout.tsx`/`page.tsx`, не через `<head>` руками.
7. Внешние скрипты — только через `next/script`.

---

## 5. `entities/` — доступ к данным

Один каталог = одна доменная сущность. Внутри — `service/<entity>Service.ts`, который является
**единственным местом**, где вызывается сгенерированный API-клиент.

Обязательная структура сервиса:

```ts
// 1) Фабрика ключей — иерархия от общего к частному, всегда `as const`
export const farmKeys = {
  all: ["farm"] as const,
  lists: () => [...farmKeys.all, "list"] as const,
  detail: (id: number) => [...farmKeys.all, "detail", id] as const,
  authContext: () => [...farmKeys.all, "auth-context"] as const,
};

// 2) Хуки чтения: use<Get><Entity>
export const useGetFarm = (farmId: number) =>
  useQuery({ queryKey: farmKeys.detail(farmId), queryFn: () => farmsApi.farmsDetail(farmId) });

// 3) Хуки записи: use<Action><Entity> + точечная инвалидация
export const useMaintainFarm = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (farmId: number) => farmsApi.farmsMaintainCreate(farmId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: farmKeys.authContext() }),
  });
};

// 4) Префетч для серверных страниц
export const prefetchFarmData = async (queryClient: QueryClient) => {
  await queryClient.prefetchQuery({
    queryKey: farmKeys.authContext(),
    queryFn: () => farmsApi.farmsByAuthContextList(),
  });
};
```

Правила:
- Ключи — **только через фабрику**, строковых литералов в `useQuery` быть не должно; иначе
  инвалидация перестаёт работать предсказуемо.
- Ключ, используемый и в префетче, и в хуке, обязан браться из одной и той же функции —
  иначе гидратация молча промахивается и данные грузятся повторно.
- `invalidateQueries({ queryKey: [] })` (инвалидация всего) — запрещено. Всегда указывать
  конкретный узел: `farmKeys.all` или уже́.
- Хук с необязательным `id` включается через `enabled: !!id`, а не через `id!` без гарда.
- Если хук объявляет параметр `options`, он обязан его прокидывать (`...options`) — иначе
  сигнатура врёт вызывающему коду.
- Опции запроса, зависящие от домена (`staleTime`, `enabled`), задаются здесь, а не в UI.
- Доменные предикаты и константы, не являющиеся частью контракта (например, статусы, которые
  бэкенд отдаёт числом), живут рядом в `service`/`model` с комментарием-объяснением:

```ts
export const RewardStatus = { Pending: 1, Claimed: 2, Expired: 3 } as const;
export type RewardStatus = (typeof RewardStatus)[keyof typeof RewardStatus];
export const isClaimable = (r?: PlayerRewardView, now = new Date()): boolean => { /* … */ };
```

- `entities/*/ui` — только для отображения самой сущности без сценария. Если появляется
  обработка кликов, мутации или маршрутизация — компонент переезжает в `features`.

---

## 6. `features/` — пользовательские сценарии

Одна фича = один сценарий («забрать награду», «привязать кошелёк», «купить донат»), а не
одна страница и не один компонент.

Раскладка внутри фичи:

| Каталог | Что кладём | Правило |
|---|---|---|
| `components/` | UI сценария | не содержат прямых вызовов API — только хуки фичи/сущности |
| `hooks/` | оркестрация: связать мутации сущности, SDK, тосты, локальный state | возвращают **явный интерфейс** (`interface UseXResult`), а не «всё подряд» |
| `lib/` | чистые функции: мапперы ошибок, билдеры payload, форматтеры | без React, без импортов UI, легко тестируются |
| `model/` | типы и константы сценария (опции, флаги, справочники) | `as const` + типизация |
| `config/` | продуктовые пороги и стили тиров/уровней | комментарий: откуда взялось число и кто его владелец |
| `types/` | локальные типы | |
| `index.ts` | публичный API фичи | явные ре-экспорты, без `export *` |

Правила:
- Хук-оркестратор — основной носитель логики сценария. Пример контракта:

```ts
interface UseClaimResult { claim: () => Promise<void>; isClaiming: boolean }
export function useClaim(seasonId: number | undefined): UseClaimResult { … }
```

- Компонент фичи не знает про axios, ключи запросов и коды ошибок бэкенда — он знает
  только `isLoading/isPending`, данные и колбэки.
- Ошибки бэкенда транслируются в i18n-ключи **в `lib/map-*-error.ts`**, отдельной чистой
  функцией с явным union-типом ключей:

```ts
export type ClaimErrorKey = "walletNotBound" | "windowClosed" | "notClaimable" | "generic";
export const mapClaimError = (error: unknown): ClaimErrorKey => { /* switch по detail */ };
```

  Так набор сообщений проверяется компилятором: `Record<ClaimErrorKey, string>`.
- Провайдеры приложения — отдельная фича `features/providers`, собранная в один
  `ComposedProvider`; `layout.tsx` подключает только его. Порядок провайдеров задаётся в
  одном месте и виден целиком.
- Мок-данные (`mocks/`) в проде не хранятся. Если нужны — только под тестами/сторибуком.

---

## 7. `shared/` — переиспользуемое

### 7.1 `shared/api`

- `generated/` — результат `npm run generate`, помечен `/* eslint-disable */`.
  **Правка руками запрещена**: при следующей генерации всё затрётся. Нужна другая форма
  ответа — меняется контракт на бэкенде и запускается генерация.
- `instance.ts` — единственная точка создания HTTP-клиента:

```ts
const httpClient = new HttpClient({ baseURL: "", withCredentials: true,
  headers: { "Content-Type": "application/json" } });

httpClient.instance.interceptors.request.use((config) => { /* auth-заголовок */ return config; });

export const farmsApi  = new Farms(httpClient);
export const usersApi  = new Users(httpClient);
```

  `baseURL: ""` + rewrite в `next.config.mjs` — запросы идут на свой домен и проксируются
  на бэкенд; это убирает CORS и прячет адрес бэкенда от браузера. Не заменять на прямой
  абсолютный URL бэкенда.
- Авторизация — только в интерсепторе, никогда в вызовах.
- Ни один слой, кроме `entities/*/service`, не импортирует `*Api` напрямую.

### 7.2 `shared/ui`

- Только презентационные компоненты: пропсы → разметка. Без запросов, без домена, без i18n-
  привязки к конкретным ключам фичи.
- Варианты оформления — через CVA (`cva` + `VariantProps`), а не через набор булевых пропсов:

```tsx
const buttonVariants = cva("base classes", {
  variants: { variant: { default: "…", ghost: "…" }, size: { sm: "…", lg: "…" } },
  defaultVariants: { variant: "default", size: "default" },
});
```

- Активное состояние — через `data-state` + `data-[state=active]:` в классах, не через
  ручную конкатенацию строк в вызывающем коде.
- Компоненты, которым нужен `ref`, оборачиваются в `forwardRef` и получают `displayName`.
- Слияние классов — только `cn()` из `@/lib/utils` (clsx + tailwind-merge), никогда
  шаблонной строкой: иначе конфликтующие tailwind-классы не схлопываются.
- Простой примитив — файл `shared/ui/button.tsx`; составной (со стилями/подкомпонентами) —
  каталог `shared/ui/<name>/index.tsx`. Одно из двух, не оба для одного компонента.

### 7.3 `shared/hooks`, `utils`, `constants`, `config`

- `hooks` — только переиспользуемые и недоменные (`use-modal`, `use-toast`, обёртка над
  SDK платформы). Обёртка над внешним SDK обязана деградировать без падения: проверять
  доступность, логировать, отдавать фолбэк.
- `utils` — чистые функции без побочных эффектов, один файл = одна тема.
- `constants/env.ts` — **единственное** место чтения `process.env` в клиентском коде:

```ts
export const ApiBaseUrl = process.env.NEXT_PUBLIC_APP_URL;
export const BotLink = process.env.NEXT_PUBLIC_TELEGRAM_ROOT || "https://…";
```

  Имя константы = смысл значения. Не называть флаг `isDev`, если в нём лежит токен.
- `config/` — конфигурация приложения; списки-константы объявлять `as const`, чтобы из них
  выводились union-типы (`export const locales = ["ru", "en"] as const`).

### 7.4 `shared/types`

- `global.d.ts` — глобальные декларации: `Window`, `ProcessEnv`, и связка i18n:

```ts
import en from "../../messages/en.json";
type Messages = typeof en;
declare global { interface IntlMessages extends Messages {} }
export {};
```

  Это даёт типобезопасные пути переводов во всём приложении.
- `css.d.ts` — расширение `React.CSSProperties` для CSS-переменных (`--delay` и т. п.),
  чтобы не писать `as any` при инлайновых стилях.
- Типы, приходящие из API, **не дублируются** — импортируются из
  `shared/api/generated/data-contracts`.

---

## 8. Server/Client компоненты

- По умолчанию всё серверное. `"use client"` ставится **на границе**: провайдер, экран фичи,
  интерактивный компонент. Не помечать клиентскими файлы-утилиты и типы.
- `"use client"` — первая строка файла, до импортов.
- Любой файл, использующий `useState/useEffect/useQuery/useTranslations`-в-клиенте,
  контекст, `window`, `document`, обработчики событий — клиентский.
- Доступ к `window`/браузерным API — только внутри `useEffect` или после проверки
  `typeof window !== "undefined"`; иначе падает SSR.
- Полифилы (например `Buffer` для крипто-библиотек) ставятся один раз в модуле, который
  их требует, с комментарием почему:

```ts
if (typeof globalThis.Buffer === "undefined") { globalThis.Buffer = BufferPolyfill as …; }
```

- Порталы (`createPortal`) — только на клиенте и только в заранее объявленный узел из layout.

---

## 9. Данные и состояние

Правила разделения состояния:

| Тип состояния | Где живёт |
|---|---|
| Серверные данные | TanStack Query (`entities/*/service`) |
| Состояние сценария (шаг, выбранный элемент) | локальный `useState` в хуке фичи |
| UI-состояние (открыта модалка) | `useModal()` из `shared/hooks` |
| Постоянное (онбординг пройден) | `shared/utils/*-storage.ts`, обёртка над `localStorage` |

- Глобального стора (Redux/Zustand) в шаблоне нет и он не вводится «на будущее» — только
  под реальную потребность, которую нельзя закрыть Query + локальным состоянием.
- Единый `QueryClient` для клиента создаётся в `ReactQueryProvider` (модульный синглтон
  допустим только на клиенте), дефолты — там же (`staleTime`).
- Блокирующая загрузка стартовых данных — отдельный компонент-«прелоадер» в провайдерах
  (`useQueries` → `Loader` → обработка 401/ошибки → `children`). Он же централизованно
  показывает экран «не авторизован» вместо разбросанных проверок по страницам.

---

## 10. i18n

- Маршруты локализованы сегментом `app/[locale]/…`; middleware `next-intl` с matcher,
  исключающим API-префикс, `_next` и файлы со статикой.
- Навигация — **только** через `@/i18n/routing` (`Link`, `useRouter`, `usePathname`,
  `redirect`), не через `next/navigation`, иначе теряется локаль в URL.
  Исключение: `usePathname` из `next/navigation`, если нужен путь **с** локалью — такой
  случай помечается комментарием.
- Тексты — только из словарей. Хардкод строк в JSX запрещён (кроме заведомо нейтральных
  символов вроде `/`, `×`).
- Два способа взять перевод:
  - в компоненте с несколькими текстами — `const t = useTranslations("<namespace>")`;
  - для одиночной подписи — компонент `<Text path="navigation.home" />` с типизированным
    путём (`Paths<IntlMessages>`).
- Структура `messages/*.json` повторяет структуру фич: `{ feature: { block: { key } } }`.
  Namespace фичи = имя фичи. Ключи ошибок — `<feature>.errors.<errorKey>` и совпадают с
  union-типом из `map-*-error.ts`.
- Все словари синхронны по набору ключей: добавил в `en.json` — добавь в остальные в том же
  коммите.

---

## 11. Стилизация

- Tailwind — основной инструмент. Порядок классов: layout → размеры → отступы → типографика
  → цвет → состояния.
- Цвета и радиусы — **через CSS-переменные**, объявленные в `app/globals.css` и
  проброшенные в `tailwind.config.ts`:

```ts
extend: { colors: { background: "var(--background)", mainColor: "var(--mainColor)" } }
```

  Прямые hex-значения в JSX не используются; исключение — единичные rgba в тенях/градиентах
  анимаций, объявленных в конфиге Tailwind.
- `content` в `tailwind.config.ts` перечисляет **все** слои (`app`, `features`, `entities`,
  `shared`) — забытый слой = вырезанные классы в проде.
- Кастомные анимации — в `theme.extend.keyframes/animation`, а не в разметке.
- SCSS-модули (`*.module.scss`) допустимы только для того, что Tailwind не покрывает
  (сложные `@keyframes` с переменными). Проверяются stylelint (`stylelint-config-standard-scss`).
- Глобальный CSS ограничен `app/globals.css`: директивы Tailwind, `:root`-переменные, темы,
  скроллбар, немногочисленные утилиты в `@layer utilities`.
- Адаптив — через `max-*` брейкпоинты, объявленные в `screens`, а не произвольные
  `@media` в JSX.

---

## 12. Конфигурация, окружение, сборка

- Все клиентские переменные — с префиксом `NEXT_PUBLIC_` и читаются **только** в
  `shared/constants/env.ts`.
- `NEXT_PUBLIC_*` инлайнятся в бандл **на этапе сборки**. Следствия, которые нужно
  зафиксировать в README проекта:
  - в Docker они передаются как `--build-arg`, а не как runtime-env;
  - секретов в них быть не может — всё попадает в публичный бандл.
- Обязательная переменная проверяется в `next.config.mjs` с внятной ошибкой, а не молча:

```js
if (!apiUrl) throw new Error("NEXT_PUBLIC_APP_URL is not set — …как починить…");
```

- Проксирование на бэкенд — через `rewrites()`; фронт всегда ходит на относительный путь.
- Кэш-заголовки для статики (`/_next/static/media/*`, изображения) задаются в `headers()`.
- `README.md` фронтенда обязан содержать: таблицу переменных (имя / обязательность / дефолт /
  назначение), локальный запуск, команду сборки образа с build-args.

---

## 13. Ошибки и уведомления

Единая цепочка:

```
axios error → map-<feature>-error.ts → ключ i18n → toast({ title, variant })
```

- `toast` вызывается из хука-оркестратора фичи, не из сервисов и не из `shared/ui`.
- Варианты тоста фиксированы (`success` / `destructive` / дефолт) — новые не плодить.
- Неизвестная ошибка всегда падает в ключ `generic` — пользователь не должен видеть
  «пустой» тост или сырой текст исключения.
- Ошибки стартовой загрузки (401 и прочее) обрабатывает прелоадер-провайдер целиком.
- `console.error` допустим только в обёртках над внешними SDK как диагностика, не как
  способ сообщить пользователю.

---

## 14. Именование

| Что | Правило | Пример |
|---|---|---|
| Файлы компонентов | `kebab-case.tsx` | `wallet-card.tsx` |
| Файлы хуков | `use-<name>.ts(x)` | `use-wallet-bind.ts` |
| Файлы утилит/lib | `kebab-case.ts` | `map-claim-error.ts` |
| Сервис сущности | `<entity>Service.ts` | `farmService.ts` |
| React-компонент | `PascalCase` | `WalletCard` |
| Хук | `use<Verb><Noun>` | `useBindWallet` |
| Query-хук | `useGet<Entity>` | `useGetFarm` |
| Mutation-хук | `use<Action><Entity>` | `useUpgradeFarm` |
| Фабрика ключей | `<entity>Keys` | `walletKeys` |
| Константы | `SCREAMING_SNAKE` или `PascalCase` для URL/ссылок | `CLAIM_GAS_NANOTON` |
| Тип результата хука | `Use<Name>Result` | `UseClaimResult` |

**Одно правило именования файлов на проект.** Смешение `PascalCase.tsx` и `kebab-case.tsx`
(как исторически сложилось в исходном проекте) ломает поиск и импорт-автокомплит —
в новом проекте выбираем `kebab-case` и не отступаем.

Экспорты: именованные для всего, кроме страниц/layout Next.js (там обязателен `default`).
`export *` не используем — только явные ре-экспорты в `index.ts`.

---

## 15. Чеклисты

### Новый эндпоинт бэкенда
1. Бэкенд опубликовал контракт → `npm run generate`.
2. Проверить diff в `shared/api/generated/` — руками там ничего не менять.
3. Добавить хук в `entities/<entity>/service/<entity>Service.ts` + ключ в фабрику.
4. Настроить инвалидацию в мутациях, которые меняют эти данные.
5. `npm run build`.

### Новая фича
1. `features/<feature>/` + `index.ts` с публичным API.
2. Чистая логика → `lib/`; константы/типы → `model/`, `config/`, `types/`.
3. Оркестрация → `hooks/use-<feature>.ts` с явным `Use…Result`.
4. UI → `components/`, примитивы берём из `shared/ui`.
5. Тексты → `messages/*.json` в namespace фичи (все языки сразу).
6. Ошибки → `lib/map-<feature>-error.ts` + `Record<ErrorKey, string>` из переводов.
7. Подключение → страница в `app/[locale]/…` или композиция в существующем экране.
8. `npm run build` + прогон сценария вручную.

### Новая страница
1. `app/[locale]/<route>/page.tsx` — серверная, тонкая.
2. Нужны данные до рендера → `prefetch…` из сервиса + `HydrationBoundary`.
3. Экран — компонент фичи, помеченный `"use client"` при необходимости.
4. Пункт навигации (если нужен) — в конфиг навигации в layout/`shared/ui/layout`.
5. Переводы заголовка и подписей.

### Новый общий компонент
1. Точно ли он недоменный? Если знает про сущность — это `features`.
2. `shared/ui/<name>.tsx` (простой) или `shared/ui/<name>/index.tsx` (составной).
3. Варианты — CVA; классы — через `cn()`; `forwardRef` + `displayName` при необходимости.
4. Никаких запросов и i18n-ключей конкретной фичи внутри.

---

## 16. Анти-паттерны (проверено на практике)

| Анти-паттерн | Чем плохо | Как правильно |
|---|---|---|
| `"use server"` в `page.tsx` | превращает экспорты в Server Actions, а не «делает страницу серверной» | ничего не писать — страницы серверные по умолчанию |
| `"use client"` + вся вёрстка прямо в `page.tsx` | страница перестаёт быть тонкой, логика не переиспользуется, ломается единообразие | экран в `features/<feature>` |
| `invalidateQueries({ queryKey: [] })` | инвалидирует весь кэш, лавина запросов | точечный ключ из фабрики |
| Строковые query-ключи вместо фабрики | инвалидация промахивается, дубли ключей | `<entity>Keys` |
| Хук принимает `options`, но не прокидывает | тихо игнорируемый `enabled`, лишние запросы | `...options` в `useQuery` |
| `id!` без `enabled: !!id` | запрос с `undefined` в URL | гард через `enabled` |
| Прямой импорт `*Api` в компоненте | обход слоя данных, дубли ключей и логики | только через сервис сущности |
| Правка файлов в `api/generated` | затрётся генерацией | менять контракт на бэкенде |
| Мок-данные в `features/*/mocks` в проде | попадают в бандл, живут вечно | убрать или держать под тестами |
| Смешение `PascalCase`/`kebab-case` в именах файлов | ломает навигацию и импорты | одно правило на проект |
| Опечатки в именах файлов (`react-quert-provider`) | вечны, потому что «работает» | переименовать сразу |
| `process.env` в компоненте | нет единой точки, переменная теряется при сборке | `shared/constants/env.ts` |
| Имя константы врёт (`isDev = NEXT_PUBLIC_TOKEN`) | читатель делает неверные выводы о безопасности | имя = смысл значения |
| `document.getElementById("modal-root")!` без гарантии узла | рантайм-краш, если layout изменили | узел объявлен в layout, контракт описан в этом документе |
| Хардкод строк в JSX | не переводится, всплывает у пользователя | `messages/*.json` |
| Конкатенация tailwind-классов шаблонной строкой | конфликтующие классы не схлопываются | `cn()` |
| Забытый слой в `content` Tailwind | классы вырезаются в проде | перечислить все слои |

---

## 17. Стартовый набор для нового проекта

Скопировать и адаптировать:

```
tsconfig.json           # paths @/*
tailwind.config.ts      # content по слоям, тема через CSS-переменные
components.json         # alias ui → @/shared/ui
postcss.config.mjs
.eslintrc.json          # next/core-web-vitals + next/typescript
.stylelintrc.json       # stylelint-config-standard-scss
next.config.mjs         # rewrites + fail-fast по обязательным env + headers
middleware.ts           # next-intl matcher
i18n/{routing,request}.ts
lib/utils.ts            # cn()
shared/api/instance.ts  # шаблон HttpClient + интерсептор авторизации
shared/types/global.d.ts, css.d.ts
generate-api.js         # URL swagger + modular/splitPathsByTag/unwrapResponseData
Dockerfile              # ARG/ENV для каждой NEXT_PUBLIC_* переменной
FRONTEND_TEMPLATE.md    # этот документ
```

Пустые каркасные каталоги создаём сразу: `app/[locale]`, `entities`, `features/providers`,
`shared/{api,ui,hooks,utils,constants,config,types,icons}`, `messages`, `public`.

### Чего в этом шаблоне нет и что стоит добавить осознанно
- **Тесты.** В исходном проекте их нет вовсе. Для нового проекта: Vitest + Testing Library,
  первыми покрываются `features/*/lib` (чистые мапперы и билдеры) и хуки-оркестраторы.
- **Prettier + pre-commit hook** — форматирование сейчас держится на договорённостях.
- **Error boundary / `error.tsx`, `not-found.tsx`, `loading.tsx`** на уровне маршрутов.
- **Многостадийный Dockerfile** (`node:*-alpine` + `output: "standalone"`) — текущий
  собирает полный образ с dev-зависимостями.
- **Аналитика/мониторинг ошибок** — единая точка в провайдерах.
