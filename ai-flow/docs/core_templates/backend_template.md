# Backend Implementation Guidelines

Единый свод правил реализации бэкенда: структура решения, слои, домен, работа с БД,
сервисы, API, конфигурация, ошибки, тесты, сборка. Документ самодостаточен — его можно
скопировать в новый репозиторий как `CLAUDE.md` / `AGENTS.md` / `docs/BACKEND_GUIDELINES.md`
и использовать как инструкцию для реализации проекта с нуля.

Дальше `Acme` — плейсхолдер имени проекта, `Order` — плейсхолдер агрегата.
Конкретная СУБД **намеренно не фиксируется** — см. раздел «Подключение к БД».

---

## 1. Технологический базис

| Область | Решение |
|---|---|
| Платформа | **.NET 10**, `TargetFramework` (`net10.0`) объявлен в **одном** месте |
| Web | ASP.NET Core, MVC-контроллеры (`AddControllers`), Swagger/OpenAPI |
| Аутентификация | **JWT Bearer** (`Microsoft.AspNetCore.Authentication.JwtBearer`), авторизация по ролям |
| Бутстрап | `Program.cs` + `HostBuilderFactory<TStartup>` + класс `Startup` (`ConfigureServices` / `Configure`) |
| ORM | EF Core + провайдер конкретной СУБД |
| Логирование | Serilog (`UseSerilog`, конфигурация из `IConfiguration`) |
| Ошибки HTTP | ProblemDetails middleware (`Hellang.Middleware.ProblemDetails` либо аналог) |
| Тесты | xUnit + NSubstitute + coverlet; интеграционные — Testcontainers + `WebApplicationFactory` |
| Пакеты | Central Package Management (`Directory.Packages.props`) + `packages.lock.json` |

Правила версий:
- `TargetFramework`, `Nullable`, `ImplicitUsings` — **только** в `Directory.Build.props`.
  Ни один `.csproj` их не переобъявляет (проверяется грепом).
- Версии пакетов — **только** в `Directory.Packages.props` (`<PackageVersion>`);
  в `.csproj` — `<PackageReference Include="..." />` **без** `Version=` (иначе `NU1008`).
- Restore зафиксирован lock-файлами; в CI — locked mode, чтобы подмена графа зависимостей
  ломала restore, а не проходила молча.

```xml
<!-- Directory.Build.props -->
<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>
    <RestoreLockedMode Condition="'$(CI)' == 'true'">true</RestoreLockedMode>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>
```

---

## 2. Структура каталогов

```
<repo-root>/
├── Acme.sln
├── Directory.Build.props          # TargetFramework / Nullable / ImplicitUsings — единственное место
├── Directory.Packages.props       # версии ВСЕХ пакетов — единственное место
├── nuget.config
├── .editorconfig
├── .dockerignore                  # исключает appsettings.protected*.json
├── docker-compose.local.yml
├── docker-compose.staging.yml
├── README.md
├── src/
│   ├── Acme.Core/                 # чистые абстракции без зависимостей
│   │   ├── Dates/                 #   ICurrentDateProvider, DefaultCurrentDateProvider
│   │   └── Persistence/           #   IRepository<TAggregate>
│   ├── Acme.Domain/               # агрегаты, сущности, VO, доменные сервисы, инварианты
│   │   ├── IUnitOfWork.cs
│   │   ├── Exceptions/            #   DomainException, ConcurrencyException
│   │   ├── ValueObjects/          #   Money, Weight, Coefficient…
│   │   ├── Orders/                #   Order.cs, IOrdersRepository.cs, Options/, дочерние сущности
│   │   └── Randoms/               #   IRandomProvider и т.п. доменные порты
│   ├── Acme.Domain.Contracts/     # enum'ы и примитивы, разделяемые наружу
│   ├── Acme.AppServices/          # прикладные сервисы (оркестрация)
│   │   ├── ServiceCollectionExtensions.cs   # AddAppServices(configuration)
│   │   ├── Exceptions/            #   AggregateNotFoundException, UnauthorizedException
│   │   └── Orders/                #   IOrdersService.cs, OrdersService.cs, OrdersMapper.cs
│   ├── Acme.AppServices.Contracts/# интерфейсы read-model'ей, потребляемых Host'ом
│   ├── Acme.Api.Contracts/        # DTO, WebRoutes, типизированные HTTP-клиенты (RestEase)
│   │   ├── WebRoutes.cs
│   │   ├── AuthConstants.cs       #   AuthRoles / AuthPolicies — единственное место строк ролей
│   │   └── Orders/{Data,Requests}/
│   ├── Acme.Persistence/          # EF Core: контекст, маппинги, репозитории, запросы, внешние API
│   │   ├── AcmeContext.cs
│   │   ├── Configurations/        #   IEntityTypeConfiguration<T>
│   │   ├── Repositories/
│   │   ├── Queries/               #   read-model'и на сыром SQL
│   │   ├── External/              #   реализации внешних HTTP-портов
│   │   └── Infrastructure/        #   EfRepositoryBase, UnitOfWork, ServiceCollectionExtensions
│   ├── Acme.Migrator/             # ЕДИНСТВЕННОЕ место миграций
│   │   ├── Migrations/
│   │   ├── DesignTimeDbContextFactory.cs
│   │   ├── Program.cs             #   Database.MigrateAsync()
│   │   └── Dockerfile
│   └── Acme.Host/                 # HTTP-хост (композиционный корень)
│       ├── Program.cs
│       ├── Controllers/
│       ├── Infrastructure/        #   Startup, HostBuilderFactory, фильтры, hosted services, guards
│       │   └── Auth/              #     JwtOptions, выдача и ротация токенов, ICurrentUserAccessor
│       ├── appsettings.json
│       ├── appsettings.protected.example.json
│       └── Dockerfile
└── tests/
    ├── Acme.Domain.UnitTests/          # чистая память, без БД и сервисов
    │   └── Infrastructure/             #   фабрики тестовых данных, детерминированные провайдеры
    ├── Acme.AppServices.UnitTests/     # сервисы на моках
    └── Acme.IntegrationTests/          # HTTP → сервис → EF → реальная БД в контейнере
        ├── Infrastructure/             #   WebApplicationFactory, фикстура контейнера, тестовая аутентификация
        ├── Controllers/
        ├── Queries/
        └── Scenarios/
```

**Дополнительные хосты** (бот, воркер, консоль) — отдельные проекты `Acme.<Name>.Host/`
с тем же бутстрапом; собственной БД у них нет — ходят в API по типизированному клиенту.

### Направление зависимостей (жёсткое)

```
Host ──► AppServices ──► Domain ──► Core
 │                                    ▲
 └──► Persistence ────────────────────┘
```

- `Domain` не ссылается ни на что, кроме `Core`.
- `Persistence` ссылается на `Domain` (+ `AppServices` для интерфейсов read-model'ей).
- `Host` — единственный, кто знает про всё, и композиционный корень.
- `*.Contracts` — только формы данных, пересекающие границу; без логики и без IO.
- Ссылка из `Domain` на `AppServices`/`Persistence`/`Host` — нарушение, ломающее слоистость.

---

## 3. Домен

### Агрегаты

- Агрегат `sealed`; два конструктора: `private` без параметров (для материализации ORM)
  и `private` доменный. Создание **только** через статическую фабрику `Initialize(...)`.
- Состояние инкапсулировано: сеттеры `private`/`init`; коллекции наружу — read-only.
- Мутации — через методы с намерением в имени (`Confirm`, `AddLine`, `Cancel`), не через сеттеры.
- Инварианты: `InvalidOperationException`; guard'ы аргументов —
  `ArgumentNullException.ThrowIfNull`, `ArgumentException.ThrowIfNullOrWhiteSpace`.
- **Никакой инфраструктуры в домене**: ни `IOptions`, ни сервисов, ни `DateTimeOffset.UtcNow`.
  Время и настройки приходят параметрами метода (`DateTimeOffset utcNow`, `TimeSpan`, VO).
- Бизнес-правила живут в агрегате, а не в сервисе и не в контроллере.

```csharp
public sealed class Order
{
    private readonly List<OrderLine> _lines = new();

    public long Id { get; set; }
    public long CustomerId { get; }
    public OrderStatus Status { get; private set; }
    public Money Total { get; private set; }
    public IReadOnlyCollection<OrderLine> Lines => _lines.AsReadOnly();
    public DateTimeOffset CreatedAtDateTime { get; }

    private Order() { }                                  // для ORM

    private Order(long customerId, DateTimeOffset utcNow)
    {
        CustomerId = customerId;
        Status = OrderStatus.Draft;
        CreatedAtDateTime = utcNow;
    }

    public static Order Initialize(long customerId, DateTimeOffset utcNow)
    {
        if (customerId <= 0)
            throw new ArgumentOutOfRangeException(nameof(customerId));

        return new Order(customerId, utcNow);
    }

    public void Confirm(DateTimeOffset utcNow, TimeSpan minimumAge)
    {
        if (Status != OrderStatus.Draft)
            throw new InvalidOperationException($"Order [{Id}] is already {Status}");

        if (utcNow - CreatedAtDateTime < minimumAge)
            throw new InvalidOperationException("Order is too young to be confirmed");

        Status = OrderStatus.Confirmed;
    }
}
```

### Value objects

- Денежные суммы, веса, коэффициенты — VO, а не «голые» `long`/`decimal`.
- `readonly record struct` с валидацией в конструкторе, перегрузками операторов и
  явными/неявными конверсиями к примитиву (нужны для маппинга в колонку).

```csharp
public readonly record struct Money
{
    public long Cents { get; }

    public Money(long cents)
    {
        if (cents < 0)
            throw new ArgumentException("Money must be non-negative", nameof(cents));
        Cents = cents;
    }

    public static Money operator +(Money a, Money b) => new(a.Cents + b.Cents);
    public static implicit operator long(Money m) => m.Cents;
    public static explicit operator Money(long cents) => new(cents);
}
```

### Доменные порты

Интерфейсы репозиториев (`IOrdersRepository`) и служебных источников (`IRandomProvider`)
объявляются **в домене**, реализуются в `Persistence`/`AppServices`.
Базовый контракт репозитория — в `Core`:

```csharp
public interface IRepository<TAggregate> where TAggregate : class
{
    void Create(TAggregate aggregate);
    ValueTask<TAggregate?> GetById(long id, CancellationToken cancellationToken = default);
    void Update(TAggregate aggregate);
}
```

---

## 4. Прикладные сервисы

Сервис — **оркестратор**, а не место бизнес-правил. Канонический сценарий:

> загрузить агрегат через `IUnitOfWork` → проверить доступ → вызвать метод агрегата →
> пометить изменения → `CommitAsync` → отдать DTO.

Правила:
- Один интерфейс `IOrdersService` + одна `sealed` реализация `OrdersService`.
- Зависимости — через конструктор; обязательные проверяются `?? throw new ArgumentNullException(...)`.
- В сервис инжектится **`IUnitOfWork`**, а не репозиторий и никогда не `DbContext`.
- Настройки — `IOptions<TOptions>`, `.Value` разворачивается в конструкторе; `IConfiguration` не инжектится.
- Время — `ICurrentDateProvider.UtcNow`, никогда `DateTimeOffset.UtcNow` напрямую
  (иначе окна/таймауты/троттлинг нельзя протестировать детерминированно).
- Владение ресурсом проверяет сервис: `resource.UserId != currentUser.Id` → `ForbiddenException`.
  Пройденная политика роли этого не заменяет.
- Каждый публичный метод заканчивается `CancellationToken cancellationToken = default`.
- Маппинг доменных типов в DTO — в отдельном статическом мапере (`OrdersMapper`), не в контроллере.

```csharp
public sealed class OrdersService : IOrdersService
{
    private readonly ILogger<OrdersService> _logger;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ICurrentDateProvider _dateProvider;
    private readonly OrderOptions _options;

    public OrdersService(
        ILogger<OrdersService> logger,
        IUnitOfWork unitOfWork,
        ICurrentDateProvider dateProvider,
        IOptions<OrderOptions> options)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _unitOfWork = unitOfWork ?? throw new ArgumentNullException(nameof(unitOfWork));
        _dateProvider = dateProvider ?? throw new ArgumentNullException(nameof(dateProvider));
        _options = options.Value ?? throw new ArgumentNullException(nameof(options));
    }

    public async Task<OrderData> Confirm(long id, CancellationToken cancellationToken = default)
    {
        var order = await _unitOfWork.OrdersRepository.GetById(id, cancellationToken)
            ?? throw new AggregateNotFoundException($"Order with id [{id}] not found");

        try
        {
            order.Confirm(_dateProvider.UtcNow, _options.MinimumAge);

            _unitOfWork.OrdersRepository.Update(order);
            await _unitOfWork.CommitAsync(cancellationToken);

            return OrdersMapper.ToOrderData(order);
        }
        catch (ConcurrencyException)
        {
            throw;                                   // конкурентность НИКОГДА не заворачивается
        }
        catch (Exception ex)
        {
            const string errorMessage = "Failed to confirm order";
            _logger.LogError(ex, errorMessage);
            throw new DomainException(errorMessage, ex);
        }
    }
}
```

### Фоновые задачи

`BackgroundService` живёт в хосте, а не в сервисном слое. Он создаёт scope на каждый тик,
резолвит scoped-сервис и **никогда не роняет хост**:

```csharp
protected override async Task ExecuteAsync(CancellationToken stoppingToken)
{
    using var timer = new PeriodicTimer(_options.TickInterval);

    while (await timer.WaitForNextTickAsync(stoppingToken))
    {
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var service = scope.ServiceProvider.GetRequiredService<IOrdersService>();
            await service.RunTick(stoppingToken);
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
            break;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Background tick failed");   // логируем и продолжаем
        }
    }
}
```

---

## 5. Работа с БД

### Подключение (СУБД-независимо)

- Строка подключения именована по имени контекста:
  `Configuration.GetConnectionString(nameof(AcmeContext))`.
- Провайдер выбирается **в одном месте** — в `AddEfPersistence`, и это единственный файл,
  который меняется при смене СУБД (PostgreSQL / MySQL-MariaDB / SQL Server / SQLite).
- Строка подключения приходит из окружения/`appsettings.protected.json`, никогда из кода
  и никогда из репозитория.
- Ограничения версий провайдера главнее версии EF: если провайдер отстаёт по major,
  весь EF-стек остаётся на версии, которую провайдер поддерживает. Перед апгрейдом EF
  сначала проверяется наличие совместимого релиза провайдера.

```csharp
public static IServiceCollection AddEfPersistence(this IServiceCollection services, string connectionString)
{
    ArgumentNullException.ThrowIfNull(services);
    if (string.IsNullOrWhiteSpace(connectionString))
        throw new ArgumentException("Connection string is required", nameof(connectionString));

    services.AddScoped<IOrdersRepository, OrdersRepository>();
    services.AddScoped<ICustomersRepository, CustomersRepository>();
    services.AddScoped<IOrdersQueries, OrdersQueries>();      // read-model'и
    services.AddScoped<IUnitOfWork, UnitOfWork>();

    services.AddDbContext<AcmeContext>((sp, options) =>
    {
        // ЕДИНСТВЕННАЯ точка привязки к конкретной СУБД
        options.UseNpgsql(connectionString, b => b.MigrationsAssembly("Acme.Migrator"))
               .UseLoggerFactory(sp.GetRequiredService<ILoggerFactory>());
    });

    return services;
}
```

### Контекст и маппинги

- Один `DbContext` на приложение. Маппинги — отдельные классы `IEntityTypeConfiguration<T>`
  в `Configurations/`, регистрируются явным `ApplyConfiguration` в `OnModelCreating`
  (явный список — видно, что забыли).
- Имена таблиц и колонок задаются **явно**, `snake_case`; таблицы — во множественном числе
  и в нижнем регистре (`orders`, `order_lines`).
- Префиксы ограничений: `ux_` — уникальный индекс, `ix_` — обычный, `fk_` — внешний ключ.
- Value objects мапятся через `.HasConversion`, дочерние сущности агрегата — через `OwnsOne`/`OwnsMany`.
- Не переопределять `DeleteBehavior` у FK owned-типов через `.Metadata` — это ломает
  сходимость снапшота модели: `migrations add` будет бесконечно генерировать один и тот же
  drop+add, а `MigrateAsync()` — падать на старте. Owned-зависимые каскадно удаляются с владельцем.

```csharp
public class OrderConfiguration : IEntityTypeConfiguration<Order>
{
    public void Configure(EntityTypeBuilder<Order> builder)
    {
        builder.ToTable("orders");
        builder.HasKey(x => x.Id);

        builder.Property(x => x.Id).HasColumnName("id");

        builder.Property(x => x.CustomerId)
            .HasColumnName("customer_id")
            .IsRequired();

        builder.HasIndex(x => x.CustomerId)
            .HasDatabaseName("ix_orders_customer_id");

        builder.Property(x => x.Total)
            .HasColumnName("total")
            .HasConversion(x => x.Cents, x => new Money(x))
            .IsRequired();

        builder.Property(x => x.CreatedAtDateTime)
            .HasColumnName("created_at_date_time")
            .IsRequired();

        builder.Property<byte[]>("Version")          // теневое поле оптимистичной блокировки
            .HasColumnName("version")
            .IsRowVersion();

        builder.HasMany(x => x.Lines)
            .WithOne()
            .HasForeignKey(x => x.OrderId)
            .HasConstraintName("fk_order_lines_orders_order_id");
    }
}
```

### Оптимистичная блокировка

Агрегаты, изменяемые конкурентно, несут теневое поле версии (`IsRowVersion()`).
Оно — источник `ConcurrencyException`; удалять его нельзя.

### Репозитории

- Общая база `EfRepositoryBase<TAggregate, TDbContext>`: `Create` = `Add`,
  `Update` = `Attach` + `State = Modified`, `GetById` = `FindAsync`.
- `GetById` переопределяется, когда нужно подтянуть дочерние коллекции (`Include`).
- Read-only выборки — `AsNoTracking()`.
- Репозиторий **никогда** не вызывает `SaveChanges`.

```csharp
public abstract class EfRepositoryBase<TAggregate, TDbContext> : IRepository<TAggregate>
    where TAggregate : class
    where TDbContext : DbContext
{
    protected TDbContext Context { get; }
    protected DbSet<TAggregate> DbSet { get; }

    protected EfRepositoryBase(TDbContext context)
    {
        Context = context;
        DbSet = context.Set<TAggregate>();
    }

    public virtual void Create(TAggregate aggregate) => DbSet.Add(aggregate);

    public virtual ValueTask<TAggregate?> GetById(long id, CancellationToken cancellationToken = default)
        => DbSet.FindAsync(id, cancellationToken);

    public virtual void Update(TAggregate aggregate)
    {
        DbSet.Attach(aggregate);
        DbSet.Entry(aggregate).State = EntityState.Modified;
    }
}
```

### Unit of Work

- Единственная точка коммита. Интерфейс — в `Domain`, реализация — в `Persistence`.
- Свойства-репозитории + `CommitAsync`.
- В `CommitAsync` инфраструктурные исключения БД транслируются в доменные:

```csharp
public async Task CommitAsync(CancellationToken cancellationToken = default)
{
    try
    {
        await _context.SaveChangesAsync(cancellationToken);
    }
    catch (DbUpdateConcurrencyException ex)
    {
        throw new ConcurrencyException("The record has been modified", ex);
    }
    catch (DbUpdateException ex)
    {
        throw new DuplicateEntryException("A unique constraint was violated", ex);
    }
}
```

Уникальный индекс + перехват `DbUpdateException` — это и есть механизм идемпотентности
для платежей/внешних callback'ов: гонка проигравшего потока превращается в понятную ошибку,
а не в дубль записи.

### Read-model'и (запросы)

- Лидерборды, отчёты, агрегации — **не репозитории**, а отдельные классы `*Queries`
  на сыром параметризованном SQL или на `AsNoTracking()`-проекциях.
- Интерфейс запроса живёт там, где его **потребитель**:
  - потребляет контроллер → `AppServices.Contracts`;
  - потребляет прикладной сервис → сам `AppServices` (иначе циклическая ссылка проектов).
  Реализация в обоих случаях — в `Persistence`.
- Пользовательский ввод **никогда** не конкатенируется в SQL: значения — только параметрами,
  имена колонок сортировки — только через `switch` по перечислению.

```csharp
var orderByColumn = leadBy switch
{
    LeadBy.Total   => "total",
    LeadBy.Created => "created_at_date_time",
    _              => "id"
};

var sql = $@"SELECT o.id, o.total
             FROM orders o
             ORDER BY o.{orderByColumn} DESC, o.id
             LIMIT @skip, @take";

var rows = await _context.Database
    .SqlQueryRaw<OrderRow>(sql, Param("skip", (page - 1) * pageSize), Param("take", pageSize))
    .ToListAsync(cancellationToken);
```

### Миграции

- Миграции лежат **только** в проекте `Acme.Migrator` (`MigrationsAssembly("Acme.Migrator")`),
  именование `yyyyMMddHHmmss_Name`.
- `DesignTimeDbContextFactory` берёт окружение из переменной среды (`DOTNET_ENVIRONMENT`)
  и строку подключения с именем этого окружения; отсутствие любой из них — падение с внятным текстом.
- Применение — запуском `Acme.Migrator` (`Database.MigrateAsync()`), не `EnsureCreated`,
  и не автоматом из веб-хоста.

---

## 6. HTTP API

- Контроллеры **тонкие**: инжектируют сервис и возвращают его `Task`/`Task<T>` напрямую.
  Ни маппинга, ни `try/catch`, ни бизнес-логики.
- Маршруты — **никогда** строковые литералы в контроллере. Все пути и сегменты — константы
  в `Api.Contracts/WebRoutes.cs`, сгруппированные по областям:
  `PublicBasePath = "/public-api"`, `InternalBasePath = "/internal-api"`, `AdminBasePath = "/admin"`.
- DTO — в `Api.Contracts`: `.../Data` — ответы, `.../Requests` — тела запросов.
- Привязка параметров явная: `[FromRoute]`, `[FromQuery]`, `[FromBody]`.
  Последний параметр действия — `CancellationToken cancellationToken = default`.
- Если есть внутренний типизированный HTTP-клиент (RestEase и т.п.), его интерфейс лежит рядом
  с DTO в `Api.Contracts` и меняется **в одном коммите** с маршрутом.

```csharp
[ApiController]
[Route(WebRoutes.Orders.Public.Path)]
[Authorize(Policy = AuthPolicies.User)]
public class OrdersController : ControllerBase
{
    private readonly IOrdersService _ordersService;

    public OrdersController(IOrdersService ordersService)
    {
        _ordersService = ordersService ?? throw new ArgumentNullException(nameof(ordersService));
    }

    [HttpGet(WebRoutes.ById)]
    public Task<OrderData?> GetById([FromRoute] long id, CancellationToken cancellationToken = default)
        => _ordersService.GetById(id, cancellationToken);

    [HttpPost(WebRoutes.Orders.Public.Confirm)]
    public Task<OrderData> Confirm([FromRoute] long id, CancellationToken cancellationToken = default)
        => _ordersService.Confirm(id, cancellationToken);
}
```

### Аутентификация и авторизация

**Единственный механизм — JWT Bearer с ролями.** Статические API-ключи (`X-*-Api-Key`) не
используются нигде: они не отзываются, не истекают, не несут идентичность и одинаковы для всех
вызывающих. Любой контур доступа выражается ролью в токене.

Одна схема аутентификации на приложение (`JwtBearerDefaults.AuthenticationScheme`), разграничение
контуров — политиками:

| Контур | Путь | Требование |
|---|---|---|
| Публичный (конечный пользователь) | `/public-api/*` | политика `AuthPolicies.User` — роль `User` |
| Внутренний (сервис→сервис) | `/internal-api/*` | политика `AuthPolicies.Service` — роль `Service` |
| Админский (человек) | `/admin/*` | политика `AuthPolicies.Admin` — роль `Admin` |

Имена ролей и политик — константы в `Api.Contracts/AuthConstants.cs`, рядом с `WebRoutes`.
Строковых литералов ролей в контроллерах и в коде выдачи токенов не бывает: опечатка в строке
роли — это молча открытый или молча закрытый эндпоинт.

```csharp
public static class AuthRoles
{
    public const string User = "user";
    public const string Service = "service";
    public const string Admin = "admin";
}

public static class AuthPolicies
{
    public const string User = nameof(User);
    public const string Service = nameof(Service);
    public const string Admin = nameof(Admin);
}
```

### Настройка проверки токена

```csharp
services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        var jwt = configuration.GetSection(nameof(JwtOptions)).Get<JwtOptions>()
            ?? throw new InvalidOperationException($"{nameof(JwtOptions)} section is missing");

        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = jwt.Issuer,
            ValidateAudience = true,
            ValidAudience = jwt.Audience,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwt.SigningKey)),
            ClockSkew = TimeSpan.FromSeconds(30),      // не дефолтные 5 минут
            RoleClaimType = ClaimTypes.Role,
            NameClaimType = ClaimTypes.NameIdentifier,
        };

        options.MapInboundClaims = false;              // иначе claim'ы переименовываются молча
    });

services.AddAuthorization(options =>
{
    options.AddPolicy(AuthPolicies.User, p => p.RequireRole(AuthRoles.User));
    options.AddPolicy(AuthPolicies.Service, p => p.RequireRole(AuthRoles.Service));
    options.AddPolicy(AuthPolicies.Admin, p => p.RequireRole(AuthRoles.Admin));

    // Fail closed: эндпоинт без явного [Authorize]/[AllowAnonymous] всё равно требует токен.
    options.FallbackPolicy = new AuthorizationPolicyBuilder()
        .RequireAuthenticatedUser()
        .Build();
});
```

Правила проверки:

- **Все четыре `Validate*` включены.** Отключённая проверка issuer/audience превращает токен
  соседнего сервиса на том же ключе в валидный здесь.
- `ClockSkew` сокращается явно: дефолтные 5 минут означают, что отозванный по истечении токен
  живёт ещё пять минут.
- `FallbackPolicy` закрывает эндпоинты, где забыли `[Authorize]`. Публичные (страница оплаты,
  health-check, приём вебхуков) помечаются `[AllowAnonymous]` **осознанно и точечно**.
- `MapInboundClaims = false` — иначе `sub` превращается в длинный WS-Federation-URI, и код,
  читающий `sub`, молча получает `null`.

### Выдача токенов

- Access-токен — короткоживущий (**15 минут**), refresh-токен — длинный (**30 дней**),
  хранится в БД в виде хеша и **отзывается**: logout, смена пароля и подозрительная активность
  инвалидируют его. Access-токен без refresh-механизма превращается в вечный, если сделать его долгим.
- Refresh **ротируется**: каждое обновление выдаёт новый refresh и гасит предыдущий. Повторное
  использование погашенного refresh — сигнал компрометации: гасится вся цепочка токенов пользователя.
- Роли кладутся в токен **на стороне сервера из БД** в момент выдачи. Роль, пришедшая в запросе
  от клиента, не читается никогда.
- Сервис-аккаунты (контур `/internal-api`) получают тот же JWT с ролью `Service` — отдельного
  механизма для них нет.
- Эндпоинт выдачи токена (`login`) — единственный, где остаётся троттлинг по IP: скользящее окно
  неудачных попыток, после `MaxFailedAttempts` за `LockoutWindow` — 429 **до** проверки пароля;
  успех сбрасывает счётчик. Время в троттлере берётся из `ICurrentDateProvider`, иначе окно
  не протестировать.
- Ответ на неуспешный вход не различает «нет такого пользователя» и «неверный пароль».

### Идентичность в коде

- Текущий пользователь читается через аксессор (`ICurrentUserAccessor`), который разворачивает
  `ClaimsPrincipal` в доменные значения (`UserId`, роли). Прикладные сервисы работают с аксессором,
  а не с `HttpContext` — иначе их нельзя юнит-тестировать и нельзя вызвать из фоновой задачи.
- **Роль — это не право на объект.** Проверка владения ресурсом делается **внутри сервиса**,
  всегда, даже после прохождения политики: `resource.UserId != currentUser.Id` →
  `ForbiddenException`. Пользователь с ролью `User` — валидный пользователь, но не владелец
  чужого заказа.
- Роли в токене — снимок на момент выдачи. Отзыв роли вступает в силу не позже истечения
  access-токена; если нужен мгновенный эффект — гасится refresh-цепочка и проверяется версия
  прав при обновлении.

```csharp
[ApiController]
[Route(WebRoutes.Orders.Public.Path)]
[Authorize(Policy = AuthPolicies.User)]
public class OrdersController : ControllerBase
```

### Секреты подписи

- `JwtOptions.SigningKey` — секрет наивысшей критичности: только из защищённой конфигурации
  или переменных окружения, минимум 32 байта, отдельный ключ на каждое окружение.
- Ключ обязателен и валидируется на старте (`IValidateOptions<JwtOptions>` + `ValidateOnStart()`,
  см. §8). Пустой или короткий ключ — падение хоста, а не «работает, но никого не пускает».
- Разные контуры **не делят** ни секрет, ни issuer с чужими сервисами.

### CORS / Swagger / детали ошибок

Это переключатели, завязанные на имя окружения, и они открываются вместе — поэтому имя окружения
валидируется по белому списку **первой строкой** `Startup.Configure`:

```csharp
public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
{
    HostingEnvironmentGuard.EnsureKnownEnvironment(env.EnvironmentName);  // Development|DockerCompose|Staging|Production

    if (env.IsDevelopment() || env.EnvironmentName == HostingEnvironmentGuard.DockerComposeEnvironmentName)
    {
        app.UseSwagger();
        app.UseSwaggerUI();
    }

    app.UseRouting();
    app.UseProblemDetails();
    app.UseCors(env.IsDevelopment() ? CorsAllowAllPolicy : CorsAllowSpecificPolicy);
    app.UseAuthentication();
    app.UseAuthorization();
    app.UseEndpoints(b => b.MapControllers());
}
```

- Никаких проверок вида `!env.IsProduction()` — опечатка в имени окружения не должна открывать
  разом Swagger, широкий CORS и детали исключений.
- Детали исключений — **только** в `Development`. `Staging` снаружи ведёт себя как `Production`.
- Продовый CORS — явный список `AllowedOrigins` + перечисленные заголовки, не `AllowAnyOrigin`.

---

## 7. Ошибки

Таксономия исключений и их отображение в HTTP:

| Исключение | Слой | Смысл | HTTP |
|---|---|---|---|
| `DomainException` | Domain | нарушено бизнес-правило | 402 (или 422 — выбрать один раз на проект) |
| `ConcurrencyException` | Domain | конкурентное изменение | 409/402 |
| `AggregateNotFoundException` | AppServices | сущность не найдена | 404/402 |
| `UnauthorizedException` | AppServices | не аутентифицирован | 401 |
| `ForbiddenException` | AppServices | аутентифицирован, но не владелец ресурса | 403 |

Правила:
- Отображение централизовано в `Startup` через ProblemDetails-`Map<>`. **Новый тип исключения
  невидим клиенту, пока не добавлен `Map<>`** — иначе наружу уходит голый 500.
- Внутри агрегата — `InvalidOperationException`/`ArgumentException`; сервис оборачивает их
  в `DomainException` общим `catch`.
- `ConcurrencyException` перехватывается и пробрасывается **первым**, до общего `catch (Exception)`.
- `ConcurrencyException` порождается **только** в `UnitOfWork.CommitAsync`; вручную не бросается.
- `AggregateNotFoundException`, `UnauthorizedException` и `ForbiddenException` бросает сервис явно.
- 401 против 403: нет валидного токена — 401 (его выдаёт сам JWT-middleware); токен валиден,
  но роль или владение не подходят — 403. Отдавать 401 на чужой ресурс неверно: клиент решит,
  что нужно перелогиниться, и уйдёт в цикл обновления токена.

```csharp
services.AddProblemDetails(options =>
{
    options.IncludeExceptionDetails = (ctx, _) =>
        ctx.RequestServices.GetRequiredService<IWebHostEnvironment>().IsDevelopment();

    options.Map<DomainException>(ex => ToProblemDetails(ex, "Business rule doesn't match", 402));
    options.Map<AggregateNotFoundException>(ex => ToProblemDetails(ex, "Not found", 404));
    options.Map<ConcurrencyException>(ex => ToProblemDetails(ex, "Concurrency error", 409));
    options.Map<UnauthorizedException>(ex => ToProblemDetails(ex, "Unauthorized", 401));
    options.Map<ForbiddenException>(ex => ToProblemDetails(ex, "Forbidden", 403));
});
```

---

## 8. Конфигурация и секреты

- Только паттерн Options. Привязка: `services.Configure<TOptions>(configuration.GetSection(nameof(TOptions)))`
  — имя секции **всегда** `nameof(TOptions)`, ключ в JSON совпадает с именем класса.
  Расхождение имени = молчаливые дефолты вместо настроек.
- Вся привязка централизована в `AddAppServices(configuration)` (плюс хост-специфичные — в `Startup`).
- Потребление — `IOptions<TOptions>`, `.Value` в конструкторе. `IConfiguration` в сервисы не инжектится.
- Если резолвленное значение нужно доменному типу — регистрируется дополнительно как синглтон:
  `services.AddSingleton<TOptions>(sp => sp.GetRequiredService<IOptions<TOptions>>().Value)`.
- Дефолты живут в C#-классе опций; `appsettings.json` их переопределяет. При изменении дефолта
  правятся **оба** места и проверяется эффективное значение.
- Секреты не коммитятся: `appsettings.protected.json` подключается как optional-файл
  + переменные окружения. В репозиторий кладётся только `.example`-шаблон.
- Файл с секретами исключается **и** из docker-контекста (`.dockerignore`), **и** из публикации
  (`<Content Remove="appsettings.protected.json" />` в `.csproj`) — web-SDK иначе кладёт
  любой `appsettings*.json` в образ. Локальный `dotnet run` файл при этом читает как обычно.

### Fail-fast валидация обязательных опций

Обязательный секрет / ключ подписи / домен, с которым что-то сверяется, **обязан** валидироваться на старте:

```csharp
public sealed class JwtOptionsValidator : IValidateOptions<JwtOptions>
{
    private const int MinimumSigningKeyBytes = 32;

    public ValidateOptionsResult Validate(string? name, JwtOptions options)
    {
        var failures = new List<string>();

        if (string.IsNullOrWhiteSpace(options.SigningKey))
            failures.Add($"{nameof(JwtOptions)}.{nameof(options.SigningKey)} is required (env: JwtOptions__SigningKey)");
        else if (Encoding.UTF8.GetByteCount(options.SigningKey) < MinimumSigningKeyBytes)
            failures.Add($"{nameof(JwtOptions)}.{nameof(options.SigningKey)} must be at least {MinimumSigningKeyBytes} bytes");

        if (string.IsNullOrWhiteSpace(options.Issuer))
            failures.Add($"{nameof(JwtOptions)}.{nameof(options.Issuer)} is required (env: JwtOptions__Issuer)");

        if (string.IsNullOrWhiteSpace(options.Audience))
            failures.Add($"{nameof(JwtOptions)}.{nameof(options.Audience)} is required (env: JwtOptions__Audience)");

        if (options.AccessTokenLifetime <= TimeSpan.Zero)
            failures.Add($"{nameof(JwtOptions)}.{nameof(options.AccessTokenLifetime)} must be positive (env: JwtOptions__AccessTokenLifetime)");

        return failures.Count > 0
            ? ValidateOptionsResult.Fail(failures)     // ВСЕ нарушения, не первое
            : ValidateOptionsResult.Success;
    }
}

// рядом с Configure<JwtOptions>(...)
services.AddSingleton<IValidateOptions<JwtOptions>, JwtOptionsValidator>();
// после AddAppServices(...) — «сконфигурировали, теперь требуем валидности»
services.AddOptions<JwtOptions>().ValidateOnStart();
```

- Сообщение называет свойство **и** его env-форму (`TOptions__Property`), но **никогда** само значение секрета.
- Валидация включена во **всех** окружениях, включая Development.
- Валидатор опций домена/сервисов живёт в `AppServices` (без зависимости от Hosting),
  валидатор хостовых опций — рядом с опциями в `Host/Infrastructure`.
- Следствие для тестов: тестовая фабрика конфигурации обязана поставлять значения для всех
  опций с `ValidateOnStart()`, иначе интеграционные тесты падают на `StartAsync`.

---

## 9. DI: регистрация и времена жизни

| Что | Lifetime |
|---|---|
| Провайдеры времени/случайности, доменные калькуляторы, генераторы, чистые стратегии | `Singleton` |
| Прикладные сервисы, репозитории, `*Queries`, `IUnitOfWork`, `DbContext` | `Scoped` |
| HTTP-клиенты внешних API | по потребителю (см. ниже) |

- У каждого слоя — свой `ServiceCollectionExtensions` с одним методом:
  `AddAppServices(IConfiguration)`, `AddEfPersistence(string connectionString)`.
  `Startup` вызывает их и больше ничего о внутренностях слоя не знает.
- Регистрации внутри метода сгруппированы комментариями: инфраструктура → домен → опции → сервисы.

### Внешние HTTP-порты

Порт (интерфейс + простые record'ы) объявляется в `AppServices`, реализация — в `Persistence`:

- Через границу порта ходят **только** примитивы/record'ы. Никаких `HttpResponseMessage`,
  `JsonDocument`, заголовков — потребитель порта должен юнит-тестироваться без знаний об HTTP.
- Если потребитель порта — синглтон, реализация обязана зависеть от `IHttpClientFactory`
  (`services.AddHttpClient("name", ...)` + `AddSingleton<IPort, Impl>()`), а **не** от инжектированного
  `HttpClient`/типизированного клиента: `AddHttpClient<T,TImpl>` регистрирует `TImpl` как transient,
  и он станет captured dependency с «вечным» handler'ом.
- Базовый адрес, таймаут — из опций в делегате `AddHttpClient`; ключ API добавляется в одном месте
  (либо в дефолтных заголовках, либо в самом клиенте — не в обоих сразу).

---

## 10. Тесты

### Уровни

| Проект | Что покрывает | Инфраструктура |
|---|---|---|
| `Acme.Domain.UnitTests` | агрегаты, VO, доменные стратегии | ничего, чистая память |
| `Acme.AppServices.UnitTests` | оркестрация сервисов | NSubstitute-моки портов |
| `Acme.IntegrationTests` | HTTP → сервис → EF → реальная БД | Testcontainers + `WebApplicationFactory` |

### Общие правила

- Стек фиксирован: xUnit + NSubstitute. Другие фреймворки/библиотеки ассертов не вводятся.
- Именование: `Method_Scenario_ExpectedResult`; тело — Arrange / Act / Assert.
- Агрегаты в тестах создаются через те же фабрики `Initialize(...)`, что и в проде; тестовые
  данные — через общие билдеры в `tests/*/Infrastructure/` (`OrderFactory.Create/CreateMany`).
- Мокаются **только** порты, которые домен объявил: `ICurrentDateProvider`, `IRandomProvider`,
  `IOptions<T>`. Недетерминированные тесты на реальном рандоме/часах — запрещены.
- Тестовые проекты не объявляют `TargetFramework` — наследуют из `Directory.Build.props`.

### Интеграционные тесты

- `AcmeWebApplicationFactory : WebApplicationFactory<Program>` поднимает хост в процессе;
  требует `public partial class Program;` после top-level statements в `Program.cs`.
- Строка подключения к контейнеру подставляется через `ConfigureAppConfiguration` **до**
  `ConfigureServices` (перекрывает `ConnectionStrings:<Context>`).
- Фоновые `IHostedService` вырезаются в `ConfigureTestServices` — тесты не должны тикать по таймеру.
- `factory.Services` — **корневой** провайдер: scoped-сервисы резолвятся только через
  `factory.Services.CreateScope().ServiceProvider`.
- Тесты, требующие Docker, помечаются `[SkippableFact]` + `Skip.IfNot(DockerAvailable)`;
  доступность демона определяется вызовом `docker info` через процесс (без лишней зависимости
  на docker-клиент). Без Docker прогон остаётся зелёным.
- Схема в контейнере накатывается **производственными миграциями** (`Database.MigrateAsync()`),
  никогда `EnsureCreated` — иначе тесты проверяют схему, которой нет в проде.
- Одна коллекционная фикстура на весь набор (контейнер + фабрика); второй `ICollectionFixture`
  на тот же контейнер поднимет лишний контейнер.
- Аутентификация в интеграционных тестах **не подменяется заглушкой**: тестовая конфигурация
  задаёт свой `JwtOptions__SigningKey`, а тесты выпускают настоящие JWT с нужными ролями через
  общий хелпер (`TokenFactory.ForUser(id)`, `TokenFactory.ForAdmin()`). Так пайплайн проверки
  токена, политики и ролевые атрибуты реально исполняются — заглушка их обходит, и регрессия
  «эндпоинт открыт всем» проходит мимо тестов.
- Обязательные негативные тесты на каждый защищённый контур: **без токена → 401**,
  **с токеном чужой роли → 403**, **с токеном другого пользователя на чужой ресурс → 403**.
  Последний ловит подмену проверки владения ролевой политикой.
- Просроченный токен проверяется отдельным тестом с явным `expires` в прошлом, а не ожиданием
  по таймеру.
- Внешние клиенты (боты, платёжные шлюзы) заменяются на `Substitute.For<>` через
  `RemoveAll<T>()` + повторную регистрацию — резолв реального клиента с пустым токеном ломает граф DI.
- Для быстрой проверки EF-логики без Docker допустим InMemory-провайдер, но только для классов
  `*Queries`/LINQ-логики, не для сценариев со схемой и ограничениями БД.

---

## 11. Сборка, верификация, деплой

**Задача считается выполненной, только если решение собирается и тесты зелёные.**
Красная сборка — незавершённая задача: чинить или докладывать о падении, но не коммитить.

```bash
dotnet build Acme.sln
dotnet test
docker compose -f docker-compose.local.yml up -d      # локальный стек
```

- Новая фича разрабатывается test-first: сначала тесты из Test Cases, недостающая реализация
  заглушается `throw new NotImplementedException()` **с телом**, чтобы решение всё время компилировалось.
  Красные тесты на зелёной сборке → замена заглушек → зелёные тесты. Коммитится только зелёное состояние.
- Dockerfile у каждого хоста свой, multi-stage (`sdk` → build/publish → `aspnet` → final),
  restore по конкретному `.csproj`, `EXPOSE` нерутового порта.
- Локальный compose привязывает порты к `127.0.0.1`, без дефолтных паролей.
- Миграции применяются отдельным контейнером/шагом `Acme.Migrator`, а не веб-хостом на старте.

---

## 12. Стиль кода

- `.editorconfig` в корне; для C#: file-scoped namespaces, `using` вне namespace, `var` везде,
  обязательные фигурные скобки, `System`-директивы первыми, отступ — таб (4).
- Публичные типы контроллеров/сервисов/агрегатов документируются XML-комментариями
  (они же питают Swagger).
- Реализации — `sealed`, если не проектируются под наследование.
- Ассинхронные методы возвращают `Task`/`ValueTask` и принимают `CancellationToken` последним
  параметром со значением по умолчанию.
- Сообщения коммитов — одна строка, ≤155 символов, без упоминания инструментов и без футеров.

---

## 13. Чек-лист новой фичи

1. **Домен**: новое правило — в агрегат/VO; никакой инфраструктуры внутри; инварианты бросают исключения.
2. **Порты**: нужны новые данные — интерфейс репозитория/запроса объявляется в `Domain`/`AppServices`.
3. **Persistence**: маппинг (`snake_case`, индексы, конверсии VO), репозиторий, миграция в `Acme.Migrator`.
4. **UnitOfWork**: новый репозиторий добавлен свойством в интерфейс и в реализацию.
5. **AppServices**: сервис-оркестратор, проверка владения, `ConcurrencyException`-rethrow-then-wrap,
   маппер в DTO, регистрация в `AddAppServices`.
6. **Опции**: новые настройки — класс `*Options`, секция `nameof`, дефолты в C#, при обязательности —
   `IValidateOptions<T>` + `ValidateOnStart()`.
7. **Contracts**: DTO запроса/ответа, константы маршрутов в `WebRoutes`, синхронный апдейт типизированного клиента.
8. **Host**: тонкий контроллер, явная политика `[Authorize(Policy = ...)]` (или осознанный
   `[AllowAnonymous]`), новый тип исключения → `Map<>` в ProblemDetails.
9. **Тесты**: доменные юнит-тесты правила + интеграционный сценарий на эндпоинт + негативные
   тесты доступа (401 без токена, 403 с чужой ролью, 403 на чужой ресурс);
   тестовая конфигурация дополнена обязательными опциями.
10. **Верификация**: `dotnet build` + `dotnet test` зелёные.
11. **Документация**: спецификация фичи и база знаний обновлены в том же изменении.

---

## 14. Антипаттерны (сводно)

- Бизнес-логика в контроллере или в прикладном сервисе вместо агрегата.
- Публичные сеттеры агрегата, отдача наружу изменяемой `List<>`, `new Order(...)` вместо `Initialize`.
- `IOptions`/сервисы/`DateTimeOffset.UtcNow` внутри домена.
- Инжект `DbContext` или конкретного репозитория в сервис в обход `IUnitOfWork`.
- `SaveChanges` в репозитории или сервисе.
- Проглоченный `ConcurrencyException` в общем `catch (Exception)`.
- Новый тип исключения без `Map<>` — клиент получает 500.
- Статический API-ключ (`X-*-Api-Key`) как механизм доступа вместо JWT с ролью.
- Строковый литерал роли в контроллере вместо константы из `AuthConstants`.
- Роль или идентификатор пользователя, прочитанные из тела запроса, заголовка или query,
  а не из проверенного токена.
- Отключённая проверка issuer/audience/lifetime; дефолтный `ClockSkew` в 5 минут.
- Ролевая политика вместо проверки владения ресурсом в сервисе.
- 401 там, где по смыслу 403 (токен валиден, прав не хватает).
- Эндпоинт без `[Authorize]` и без осознанного `[AllowAnonymous]`.
- Долгоживущий access-токен вместо пары access + отзываемый ротируемый refresh.
- Подмена аутентификации заглушкой в интеграционных тестах вместо выпуска настоящего JWT.
- Конкатенация пользовательского ввода в SQL; сортировка по имени колонки из запроса.
- Миграция, добавленная не в проект миграторов; `EnsureCreated` вместо миграций.
- Строковые литералы маршрутов в контроллерах; изменение маршрута без правки клиента.
- Инжект `IConfiguration` в сервис; секция конфигурации с именем ≠ имени класса опций.
- Обязательная настройка, деградирующая при первом использовании вместо падения на старте.
- Значение секрета в тексте ошибки валидации.
- `Version=` на `PackageReference` при включённом CPM; `TargetFramework` в `.csproj`.
- Ссылка `Domain → AppServices/Persistence/Host`.
- Объявление задачи выполненной без успешных `build` и `test`.
