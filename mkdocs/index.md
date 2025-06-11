
# Welcome to AuraConnect Docs

This wiki helps developers quickly understand, setup, and contribute to AuraConnect.

## 🧰 Getting Started

### Install MkDocs & Material Theme

```bash
pip install mkdocs mkdocs-material
```

### Run the Docs Locally

```bash
mkdocs serve
```

Open your browser and go to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 📊 Platform Architecture

![AuraConnect Architecture](AuraConnect_Architecture_ColorCoded.png)

This diagram outlines the high-level structure of the platform including:
- UI (Staff Dashboard, Mobile App)
- Logic (Backend API, Modules)
- AI Agent Layer
- Infra (Database, Cloud Services, CI/CD)

---

## 🌐 Deploy to GitHub Pages

```bash
mkdocs gh-deploy
```

This will:
- Build the static site
- Push it to your GitHub repo’s `gh-pages` branch
- Make it live at: `https://<your-github-username>.github.io/auraconnect/`
