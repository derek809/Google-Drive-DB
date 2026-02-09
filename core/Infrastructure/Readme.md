Infrastructure/

Purpose: The system foundation. It provides essential services, persistent storage, and global configuration required for the entire bot to function.



Flow

System Initialization \& Health Check

System Start

&nbsp;  ↓

m1\_config.validate\_config()

&nbsp;  ├─→ Checks: Credentials \& API Keys (Gmail, Sheets, Claude)

&nbsp;  │   └─→ FAIL: Logs error and exits

&nbsp;  │

&nbsp;  └─→ SUCCESS: Initialize Core Services

&nbsp;      ↓

db\_manager.\_ensure\_schema()

&nbsp;  ├─→ Action: Creates SQLite tables (Queue, Tasks, Skills)

&nbsp;  └─→ Action: Runs pending migrations

&nbsp;      ↓

observability.HealthChecker.check\_all()

&nbsp;  ├─→ Monitors: Latency and API cost per model

&nbsp;  └─→ Safety: Activates Circuit Breakers if services fail

Components

Action Registry (actions.py): The formal contract for every executable skill. It defines required parameters and risk levels (Low/Medium/High).



Database Manager (db\_manager.py): Central handler for the mode4.db SQLite instance. Manages message queues, task persistence, and skill storage.



Observability (observability.py): Monitors health without external dependencies. It tracks performance metrics and handles self-healing via circuit breakers.



Config (m1\_config.py): The single source of truth for environment variables and feature flags.

