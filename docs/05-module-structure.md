# Structure de modules / arborescence de projet

## Principe : structure par couche À L'INTÉRIEUR de chaque bounded context (pas l'inverse)

Une erreur fréquente est d'organiser par couche technique en premier (`/controllers`, `/services`, `/repositories` à la racine, mélangeant tous les contextes). On organise **d'abord par contexte métier**, puis par couche à l'intérieur — ça respecte la frontière DDD et rend chaque contexte potentiellement extractible en service séparé plus tard.

```
/src
  /shared-kernel
    /rules-engine
      /domain
        RuleSet.ts
        Rule.ts
        IRuleEvaluator.ts        (port)
        ConfidenceScore.ts       (value object)
      /application
        EvaluateMessageUseCase.ts
      /infrastructure
        evaluators/
          KeywordMatchEvaluator.ts
          AmountPatternEvaluator.ts
          OcrPaymentProofEvaluator.ts   (V2)
        RuleConfigRepository.ts        (implémente IRuleConfigRepository)
    /identity
      /domain
        Merchant.ts
        SubscriptionPlan.ts
      /application
      /infrastructure

    /access-control
      /domain
        Role.ts                    (Aggregate Root)
        RoleAssignment.ts           (Aggregate Root)
        Permission.ts               (value object)
        AccessScope.ts              (value object)
        IPermissionChecker.ts       (port)
        IRoleRepository.ts
      /application
        CreateRoleUseCase.ts
        AssignRoleToUserUseCase.ts
        RevokeRoleFromUserUseCase.ts
        CheckPermissionUseCase.ts
      /infrastructure
        PostgresRoleRepository.ts
        RedisPermissionCache.ts
      /presentation
        rest/
          RoleController.ts

  /platform
    /middleware                    (transverse, appliqué à toutes les routes)
      RequestIdMiddleware.ts
      ExceptionHandlingMiddleware.ts
      AuthenticationMiddleware.ts
      TenantIsolationMiddleware.ts
      PermissionMiddleware.ts
      RateLimitMiddleware.ts
      AuditLoggingMiddleware.ts

  /contexts
    /platform-connectors
      /domain
        PlatformConnection.ts
        IPlatformConnector.ts     (port)
        IMessageFetcher.ts        (port, ISP)
        IMessageSender.ts         (port, ISP)
      /application
        SyncMessagesUseCase.ts
      /infrastructure
        connectors/
          whatsapp/
            WhatsAppConnector.ts
            WhatsAppApiClient.ts
          instagram/
            InstagramConnector.ts
      /presentation
        webhooks/
          WhatsAppWebhookHandler.ts
          InstagramWebhookHandler.ts

    /backup
      /domain
        BackupSnapshot.ts
        IBackupRepository.ts
      /application
        CreateDailySnapshotUseCase.ts
        RestoreFromSnapshotUseCase.ts
      /infrastructure
        PostgresBackupRepository.ts
        ObjectStorageAdapter.ts
      /presentation
        rest/
          BackupController.ts

    /order-detection
      /domain
        Order.ts                  (Aggregate Root)
        Reminder.ts
        Money.ts                  (value object)
        OrderStatus.ts             (value object / enum)
        IOrderRepository.ts
      /application
        DetectOrderUseCase.ts
        ScheduleReminderUseCase.ts
        GetDormantMoneyDashboardUseCase.ts
      /infrastructure
        PostgresOrderRepository.ts
        RedisReminderScheduler.ts
      /presentation
        rest/
          OrderController.ts
          DashboardController.ts

    /crm
      /domain
        Contact.ts                 (Aggregate Root)
        CRMSegment.ts
        LoyaltyScoreCalculator.ts  (domain service)
        SegmentMembershipCalculator.ts (domain service)
      /application
        UpdateContactFromMessageUseCase.ts
        SendBulkMessageUseCase.ts
      /infrastructure
        PostgresContactRepository.ts
        RedisSegmentCache.ts
      /presentation
        rest/
          ContactController.ts
          SegmentController.ts

  /platform (infrastructure transverse, pas un contexte métier)
    /event-bus
      IEventPublisher.ts
      RedisEventPublisher.ts
    /persistence
      DatabaseConnection.ts
      migrations/
    /config
      environment.ts
    /di                            (composition root — injection de dépendances)
      container.ts

/docs                              (ce dossier — toujours à jour, référencé par copilot-instructions.md)
/tests
  /unit          (domain + application, sans I/O — rapides, nombreux)
  /integration   (infrastructure, avec vraie DB de test)
  /e2e           (parcours complet, peu nombreux)
```

## Règles de nommage strictes

- Les interfaces (ports) sont préfixées `I` : `IOrderRepository`, `IRuleEvaluator`.
- Les Use Cases sont suffixés `UseCase` : `DetectOrderUseCase`.
- Les implémentations d'infrastructure indiquent la techno : `PostgresOrderRepository`, `RedisReminderScheduler` — jamais un nom générique ambigu comme `OrderRepositoryImpl`.
- Les Value Objects sont des noms de concept métier, jamais suffixés `VO` dans le nom de fichier (le suffixe est juste pour cette documentation).

## Règle absolue pour Copilot

Avant de créer un nouveau fichier, toujours se demander : "dans quel bounded context et dans quelle couche ce code vit-il ?" Si la réponse n'est pas évidente en 5 secondes, c'est que la responsabilité est mal définie — reposer la question plutôt que de deviner un emplacement.
