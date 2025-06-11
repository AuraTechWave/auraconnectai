# AuraConnect – White-Labeling Support Module

## 1. 🧩 Overview & Goals

This module enables platform branding to be customized per client (restaurant group, franchise, or white-label partner). It supports themes, logos, color schemes, domains, and even branded mobile apps.

**Goals:**

- Allow each tenant to brand the UI with their logo and color scheme
- Enable custom domains and white-label subdomains
- Support theming overrides for web & mobile clients
- Simplify branding configuration via admin dashboard

---

## 2. 🖼️ Branding Elements

- Logo & Favicon
- Color Palette (primary, secondary, background)
- Font family
- Domain (custom or subdomain)
- Footer/contact details

---

## 3. 🧱 Architecture Overview

**Core Services:**

- `BrandingService` – Stores and applies tenant branding config
- `ThemeEngine` – Compiles and renders tenant-specific styles
- `DomainRouter` – Maps incoming requests to tenant
- `MobilePackager` – For branded mobile builds (optional CI toolchain)

```
[User Request] ─▶ [DomainRouter] ─▶ [Tenant ID]
                        │
                        ▼
               [BrandingService] ─▶ [ThemeEngine / UI Layer]
```

---

## 4. 🔄 Flowcharts

### UI Branding Load Flow:

1. User opens `mybrand.auraconnect.ai`
2. DomainRouter maps to tenant ID
3. BrandingService fetches config
4. ThemeEngine renders theme tokens
5. UI applies theme dynamically

### Admin Branding Setup Flow:

1. Admin opens Branding Settings
2. Uploads logo, selects colors/fonts
3. Clicks preview and confirms
4. Config is saved and rendered immediately

---

## 5. 📡 API Endpoints

### Branding Config

- `GET /branding/:tenantId` – fetch branding
- `POST /branding` – update config

### Domain Mapping

- `POST /branding/domain` – link domain
- `GET /branding/domain/:tenantId`

---

## 6. 🗃️ Database Schema

### Table: `branding_configs`

\| id | tenant\_id | logo\_url | primary\_color | font | updated\_at |

### Table: `custom_domains`

\| id | tenant\_id | domain | verified | created\_at |

---

## 7. 🛠️ Code Stub

```ts
// branding.service.ts
app.get("/branding/:tenantId", async (req, res) => {
  const config = await db.query("SELECT * FROM branding_configs WHERE tenant_id = $1", [req.params.tenantId]);
  res.json(config);
});
```

---

## 8. 📘 Developer Notes

- Consider caching themes in CDN for performance
- Support fallbacks (e.g., default logo if none provided)
- Ensure safe rendering of styles to avoid injection
- Mobile packaging can be CI/CD-based with env config injection

---

## ✅ Summary

White-labeling makes AuraConnect adaptable to franchises and partners. This module adds a vital layer of customization, making each tenant’s experience feel fully branded.

➡️ Next up: **Offline Sync for Mobile**

