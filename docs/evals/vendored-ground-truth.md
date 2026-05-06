# Vendored Repo Ground Truth

This report inventories declared modules, observed external imports, and the current block footprint for the vendored repo corpus. It supports the **block gold** rail (`gold_block_benchmark*.json`), not the **evidence-benchmark** rail (`evidence_questions.json`); see `gold-standards.md` for both.

## Elysia-routing-controllers

- Path: `vendor/github-repos/Elysia-routing-controllers`
- Files scanned: 25
- Manifests: `package.json`
- Declared modules: 14
- Used external modules: 9

### Swappable Declared Modules

_None detected_

### Swappable Used Modules

_None detected_

### Repo Block Footprint

- `data_persistence` (high, evidence 12)
- `search_architecture` (high, evidence 11)
- `background_processing` (high, evidence 4)
- `system_telemetry` (high, evidence 3)
- `connectivity_layer` (medium, evidence 2)
- `access_control` (low, evidence 1)
- `asset_delivery` (medium, evidence 1)
- `edge_support` (low, evidence 1)
- `error_boundaries` (medium, evidence 1)
- `experimentation` (low, evidence 1)
- `global_interface` (medium, evidence 1)
- `security_ops` (low, evidence 1)

### Undeclared But Used Modules

_None_

## bun-api

- Path: `vendor/github-repos/bun-api`
- Files scanned: 89
- Manifests: `apps/backend/package.json`, `apps/frontend/package.json`, `package.json`
- Declared modules: 77
- Used external modules: 61

### Swappable Declared Modules

- `@mrleebo/prisma-ast` -> data_persistence
- `@prisma/client` -> data_persistence
- `@radix-ui/react-accordion` -> core_rendering, visual_systems
- `@radix-ui/react-alert-dialog` -> core_rendering, visual_systems
- `@radix-ui/react-aspect-ratio` -> core_rendering, visual_systems
- `@radix-ui/react-avatar` -> core_rendering, visual_systems
- `@radix-ui/react-checkbox` -> core_rendering, visual_systems
- `@radix-ui/react-collapsible` -> core_rendering, visual_systems
- `@radix-ui/react-context-menu` -> core_rendering, visual_systems
- `@radix-ui/react-dialog` -> core_rendering, visual_systems
- `@radix-ui/react-dropdown-menu` -> core_rendering, visual_systems
- `@radix-ui/react-hover-card` -> core_rendering, visual_systems
- `@radix-ui/react-label` -> core_rendering, visual_systems
- `@radix-ui/react-menubar` -> core_rendering, visual_systems
- `@radix-ui/react-navigation-menu` -> core_rendering, visual_systems
- `@radix-ui/react-popover` -> core_rendering, visual_systems
- `@radix-ui/react-progress` -> core_rendering, visual_systems
- `@radix-ui/react-radio-group` -> core_rendering, visual_systems
- `@radix-ui/react-scroll-area` -> core_rendering, visual_systems
- `@radix-ui/react-select` -> core_rendering, visual_systems
- `@radix-ui/react-separator` -> core_rendering, visual_systems
- `@radix-ui/react-slider` -> core_rendering, visual_systems
- `@radix-ui/react-slot` -> core_rendering, visual_systems
- `@radix-ui/react-switch` -> core_rendering, visual_systems
- `@radix-ui/react-tabs` -> core_rendering, visual_systems
- `@radix-ui/react-toggle` -> core_rendering, visual_systems
- `@radix-ui/react-toggle-group` -> core_rendering, visual_systems
- `@radix-ui/react-tooltip` -> core_rendering, visual_systems
- `@tailwindcss/vite` -> asset_delivery, visual_systems
- `@tanstack/react-query` -> core_rendering
- `@types/react` -> core_rendering
- `@types/react-dom` -> core_rendering
- `@vitejs/plugin-react-swc` -> core_rendering, asset_delivery
- `better-auth` -> identity_ui
- `class-variance-authority` -> identity_ui
- `embla-carousel-react` -> core_rendering
- `eslint-plugin-react-hooks` -> core_rendering
- `eslint-plugin-react-refresh` -> core_rendering
- `ioredis` -> data_persistence
- `lucide-react` -> core_rendering
- `next-themes` -> core_rendering
- `prisma` -> data_persistence
- `prismabox` -> data_persistence
- `react` -> core_rendering
- `react-day-picker` -> core_rendering
- `react-dom` -> core_rendering
- `react-hook-form` -> core_rendering, interaction_design
- `react-resizable-panels` -> core_rendering
- `tailwindcss` -> visual_systems
- `vite` -> asset_delivery
- `zod` -> interaction_design

### Swappable Used Modules

- `@mrleebo/prisma-ast` -> data_persistence
- `@radix-ui/react-accordion` -> core_rendering, visual_systems
- `@radix-ui/react-alert-dialog` -> core_rendering, visual_systems
- `@radix-ui/react-aspect-ratio` -> core_rendering, visual_systems
- `@radix-ui/react-avatar` -> core_rendering, visual_systems
- `@radix-ui/react-checkbox` -> core_rendering, visual_systems
- `@radix-ui/react-collapsible` -> core_rendering, visual_systems
- `@radix-ui/react-context-menu` -> core_rendering, visual_systems
- `@radix-ui/react-dialog` -> core_rendering, visual_systems
- `@radix-ui/react-dropdown-menu` -> core_rendering, visual_systems
- `@radix-ui/react-hover-card` -> core_rendering, visual_systems
- `@radix-ui/react-label` -> core_rendering, visual_systems
- `@radix-ui/react-menubar` -> core_rendering, visual_systems
- `@radix-ui/react-navigation-menu` -> core_rendering, visual_systems
- `@radix-ui/react-popover` -> core_rendering, visual_systems
- `@radix-ui/react-progress` -> core_rendering, visual_systems
- `@radix-ui/react-radio-group` -> core_rendering, visual_systems
- `@radix-ui/react-scroll-area` -> core_rendering, visual_systems
- `@radix-ui/react-select` -> core_rendering, visual_systems
- `@radix-ui/react-separator` -> core_rendering, visual_systems
- `@radix-ui/react-slider` -> core_rendering, visual_systems
- `@radix-ui/react-slot` -> core_rendering, visual_systems
- `@radix-ui/react-switch` -> core_rendering, visual_systems
- `@radix-ui/react-tabs` -> core_rendering, visual_systems
- `@radix-ui/react-toggle` -> core_rendering, visual_systems
- `@radix-ui/react-toggle-group` -> core_rendering, visual_systems
- `@radix-ui/react-tooltip` -> core_rendering, visual_systems
- `@tailwindcss/vite` -> asset_delivery, visual_systems
- `@tanstack/react-query` -> core_rendering
- `@vitejs/plugin-react-swc` -> core_rendering, asset_delivery
- `better-auth` -> identity_ui
- `class-variance-authority` -> identity_ui
- `eslint-plugin-react-hooks` -> core_rendering
- `eslint-plugin-react-refresh` -> core_rendering
- `ioredis` -> data_persistence
- `lucide-react` -> core_rendering
- `next-themes` -> core_rendering
- `react` -> core_rendering
- `react-day-picker` -> core_rendering
- `react-dom` -> core_rendering
- `react-hook-form` -> core_rendering, interaction_design
- `react-resizable-panels` -> core_rendering
- `vite` -> asset_delivery
- `zod` -> interaction_design

### Repo Block Footprint

- `core_rendering` (high, evidence 109)
- `visual_systems` (high, evidence 85)
- `global_interface` (high, evidence 31)
- `experimentation` (high, evidence 22)
- `identity_ui` (high, evidence 20)
- `data_persistence` (high, evidence 19)
- `interaction_design` (high, evidence 10)
- `state_management` (high, evidence 10)
- `asset_delivery` (high, evidence 9)
- `user_observability` (high, evidence 9)
- `search_architecture` (high, evidence 7)
- `connectivity_layer` (high, evidence 3)

### Undeclared But Used Modules

_None_

## clean-elysia

- Path: `vendor/github-repos/clean-elysia`
- Files scanned: 127
- Manifests: `package.json`
- Declared modules: 42
- Used external modules: 27

### Swappable Declared Modules

- `@types/pg` -> data_persistence
- `bullmq` -> background_processing
- `elysia-rate-limit` -> traffic_control
- `ioredis` -> data_persistence
- `pg` -> data_persistence
- `pino` -> system_telemetry
- `pino-pretty` -> system_telemetry

### Swappable Used Modules

- `bullmq` -> background_processing
- `elysia-rate-limit` -> traffic_control
- `ioredis` -> data_persistence
- `pg` -> data_persistence
- `pino` -> system_telemetry

### Repo Block Footprint

- `data_persistence` (high, evidence 58)
- `search_architecture` (high, evidence 48)
- `access_control` (high, evidence 20)
- `global_interface` (high, evidence 13)
- `system_telemetry` (high, evidence 11)
- `security_ops` (high, evidence 9)
- `background_processing` (high, evidence 8)
- `connectivity_layer` (high, evidence 8)
- `error_boundaries` (high, evidence 8)
- `identity_ui` (high, evidence 7)
- `experimentation` (high, evidence 5)
- `persistence_strategy` (high, evidence 3)

### Undeclared But Used Modules

- `@eslint/js`
- `globals`

## elysia-kickstart

- Path: `vendor/github-repos/elysia-kickstart`
- Files scanned: 27
- Manifests: `package.json`
- Declared modules: 28
- Used external modules: 17

### Swappable Declared Modules

- `@auth/core` -> identity_ui
- `@auth/drizzle-adapter` -> identity_ui
- `@tailwindcss/typography` -> visual_systems
- `prettier-plugin-tailwindcss` -> visual_systems
- `tailwindcss` -> visual_systems
- `tailwindcss-animate` -> visual_systems
- `zod` -> interaction_design

### Swappable Used Modules

- `@auth/core` -> identity_ui
- `@auth/drizzle-adapter` -> identity_ui
- `@tailwindcss/typography` -> visual_systems
- `tailwindcss` -> visual_systems
- `tailwindcss-animate` -> visual_systems
- `zod` -> interaction_design

### Repo Block Footprint

- `data_persistence` (high, evidence 11)
- `identity_ui` (high, evidence 11)
- `visual_systems` (high, evidence 9)
- `search_architecture` (high, evidence 6)
- `access_control` (high, evidence 4)
- `connectivity_layer` (high, evidence 4)
- `core_rendering` (high, evidence 4)
- `interaction_design` (high, evidence 4)
- `state_management` (high, evidence 4)
- `analytical_intelligence` (medium, evidence 3)
- `background_processing` (medium, evidence 2)
- `global_interface` (medium, evidence 2)

### Undeclared But Used Modules

_None_

## elysia-supabase-tempate

- Path: `vendor/github-repos/elysia-supabase-tempate`
- Files scanned: 32
- Manifests: `package.json`
- Declared modules: 29
- Used external modules: 17

### Swappable Declared Modules

- `@prisma/adapter-pg` -> data_persistence
- `@prisma/client` -> data_persistence
- `@react-email/components` -> core_rendering
- `@react-email/preview-server` -> core_rendering
- `@react-email/render` -> core_rendering
- `@supabase/supabase-js` -> data_persistence
- `@types/pg` -> data_persistence
- `@types/react` -> core_rendering
- `@types/react-dom` -> core_rendering
- `elysia-rate-limit` -> traffic_control
- `esbuild` -> asset_delivery
- `pg` -> data_persistence
- `prisma` -> data_persistence
- `react` -> core_rendering
- `react-dom` -> core_rendering
- `zod` -> interaction_design

### Swappable Used Modules

- `@prisma/adapter-pg` -> data_persistence
- `@prisma/client` -> data_persistence
- `@prisma/config` -> data_persistence
- `@react-email/render` -> core_rendering
- `@supabase/supabase-js` -> data_persistence
- `elysia-rate-limit` -> traffic_control
- `pg` -> data_persistence
- `react` -> core_rendering
- `zod` -> interaction_design

### Repo Block Footprint

- `data_persistence` (high, evidence 23)
- `core_rendering` (high, evidence 12)
- `background_processing` (high, evidence 7)
- `interaction_design` (high, evidence 7)
- `system_telemetry` (high, evidence 7)
- `identity_ui` (high, evidence 6)
- `connectivity_layer` (high, evidence 5)
- `access_control` (high, evidence 4)
- `security_ops` (high, evidence 4)
- `state_management` (high, evidence 4)
- `analytical_intelligence` (medium, evidence 3)
- `asset_delivery` (high, evidence 3)

### Undeclared But Used Modules

- `@prisma/config`
